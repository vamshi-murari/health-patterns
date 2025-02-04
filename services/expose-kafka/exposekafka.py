from kafka import KafkaConsumer
from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from flask import Flask, request
from flask import jsonify
from datetime import datetime
import json
import logging
import os
import time
import uuid

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

kafkauser = os.getenv("KAFKAUSER")
kafkapw = os.getenv("KAFKAPW")
kafkabootstrap = os.getenv("KAFKABOOTSTRAP")

# create the kafka topics before use
initial_topics = os.getenv("INITTOPICS", "")  #empty list if missing
numpartitions = os.getenv("INITTOPICNUMPARTITIONS", "1")
if len(numpartitions) == 0:
    numpartitions = 1
else:
    numpartitions = int(numpartitions)

replication = os.getenv("INITTOPICREPLICATION", "1")
if len(replication) == 0:
    replication = 1
else:
    replication = int(replication)

init_topics = initial_topics.replace(",", " ")
topiclist = init_topics.split()

app.logger.info("Attempting to connect to Kafka server")
last_recorded_time = round(time.time() * 1000)

while True:
    try:
        KafkaConsumer(bootstrap_servers=kafkabootstrap,
                                 sasl_mechanism="PLAIN", sasl_plain_username=kafkauser, sasl_plain_password=kafkapw)
        break
    except Exception as e:
        current_time = round(time.time() * 1000)
        # If the Kafka server isn't up for any reason, we'll print a message every minute until it comes up.
        if current_time - last_recorded_time > 10 * 1000:
            app.logger.error(f"Unable to connect Kafka server: {e}")
            app.logger.info("Retrying connection to Kafka server...")
            last_recorded_time = current_time
        # Even though we only print a message every 10 seconds, we'll try to connect every 5 seconds
        # to minimize container startup time.
        time.sleep(5)

# kafka is now up and running

initconsumer = KafkaConsumer(bootstrap_servers=kafkabootstrap,
                         sasl_mechanism="PLAIN", sasl_plain_username=kafkauser, sasl_plain_password=kafkapw)

existing_topics = initconsumer.topics()

init_admin_client = KafkaAdminClient(
    bootstrap_servers=kafkabootstrap,
    client_id="initbootstrapclient"
)

new_topic_list = []
for new_topic in topiclist:
    if new_topic not in existing_topics:
        new_topic_list.append(NewTopic(name=new_topic, num_partitions=numpartitions, replication_factor=replication))
init_admin_client.create_topics(new_topics=new_topic_list, validate_only=False)

existing_topics = initconsumer.topics() #reset the existing_topics since new ones may have been added

for atopic in existing_topics:
    initconsumer.partitions_for_topic(atopic) # populate cache for each topic

ready = open("ready","w")  # this file will notify the readiness probe
app.logger.info("Kafka topics loaded-readiness probe ok")

@app.route("/healthcheck", methods=['GET'])
def healthcheck():

    now = datetime.now()
    current_time_date = now.strftime("%Y-%m-%d %H:%M:%S")
    return generate_response(200, {"message": "Kafka tool service is running..." + current_time_date + "GMT"})

@app.route("/", methods=['GET'])
def listorconsumetopics():
    topic = ""
    if 'topic' in request.args:
        topic = request.args.get("topic")

    if len(topic) == 0: #topic arg not present so do topiclist
        consumer = KafkaConsumer(bootstrap_servers=kafkabootstrap,
                                 sasl_mechanism="PLAIN", sasl_plain_username=kafkauser, sasl_plain_password=kafkapw)

        existingtopics = consumer.topics()

        return generate_response(200, {"topics": str(existingtopics)})

    #consume the given topic
    consumer = KafkaConsumer(topic, bootstrap_servers=kafkabootstrap,
                             sasl_mechanism="PLAIN", sasl_plain_username=kafkauser, sasl_plain_password=kafkapw,
                             consumer_timeout_ms=2000)

    existingtopics = consumer.topics()
    if topic not in existingtopics:
        return generate_response(400, {"message": "Topic not found: selected topic does not exist"})

    consumer.topics()
    consumer.seek_to_beginning()

    msglist = []
    for msg in consumer:
        msglist.append("\nMessage: " + str(msg))

    nummessages = len(msglist)
    messages = "\n".join(msglist)

    return generate_response(200, {"topic": topic,
                                   "nummessages": nummessages,
                                   "data": messages})

@app.route("/", methods=['POST'])
def produce():
    resolveterminology = request.headers.get("ResolveTerminology", "false")
    deidentifydata = request.headers.get("DeidentifyData", "false")
    runascvd = request.headers.get("RunASCVD", "false")
    add_nlp_insights = request.headers.get("AddNLPInsights", "false")
    resourceid = request.headers.get("ResourceId", "")
    out_topic = request.args.get("response_topic", None)
    failure_topic = request.args.get("failure_topic", None)
    run_async = out_topic is None

    headers = [
                ("ResolveTerminology",bytes(resolveterminology, 'utf-8')),
                ("DeidentifyData",bytes(deidentifydata, 'utf-8')),
                ("RunASCVD",bytes(runascvd, 'utf-8')),
                ("AddNLPInsights",bytes(add_nlp_insights, 'utf-8'))
               ]

    if len(resourceid) > 0:
        headers.append(("ResourceId", bytes(resourceid, 'utf-8')))

    if not run_async:
        kafka_key = str(uuid.uuid1())
        headers.append(("kafka_key", bytes(kafka_key, 'utf-8')))

    topic = ""
    if 'topic' in request.args:
        topic = request.args.get("topic")

    if len(topic) == 0:
        #no topic 400 error
        return generate_response(400, {"message": "Topic not found: must include a topic for produce (POST)"})

    post_data = request.data.decode("utf-8")

    producer = KafkaProducer(bootstrap_servers=kafkabootstrap, max_request_size=10000000)

    producer.send(topic, value=bytes(post_data, 'utf-8'), headers=headers)
    producer.flush()

    if run_async:
        return generate_response(200, {"topic": topic,
                                       "headers": str(headers),
                                       "data": post_data[0:25] + "... " + str(len(post_data)) + " chars"})

    # Wait for pipeline to respond
    out_consumer = KafkaConsumer(
        out_topic,
        bootstrap_servers = kafkabootstrap,
        sasl_mechanism = "PLAIN",
        sasl_plain_username = kafkauser,
        sasl_plain_password = kafkapw,
        consumer_timeout_ms = 2000
        )
    out_consumer.topics()
    out_consumer.seek_to_beginning()

    failure_consumer = None
    if failure_topic is not None:
        failure_consumer = KafkaConsumer(
            failure_topic,
            bootstrap_servers = kafkabootstrap,
            sasl_mechanism = "PLAIN",
            sasl_plain_username = kafkauser,
            sasl_plain_password = kafkapw,
            consumer_timeout_ms = 2000
            )
        failure_consumer.topics()
        failure_consumer.seek_to_beginning()

    start_time = time.time()
    timeout = int(os.getenv("REQUEST_TIMEOUT", "30"))

    while time.time() < start_time + timeout:
        response = find_message(out_consumer, kafka_key)
        if response is not None:
            return response

        if failure_consumer is not None:
            response = find_message(failure_consumer, kafka_key)
            if response is not None:
                if response.status_code == 200:
                    response.status_code = 400
                return response

    # Timeout
    return generate_response(408, {"topic": topic,
                                   "headers": str(headers),
                                   "data": post_data[0:25] + "... " + str(len(post_data)) + " chars"})

def find_message(consumer, kafka_key):
    for msg in consumer:
        match = False
        status_code = 200
        for k,v in msg.headers:
            if k == 'kafka_key':
                if v.decode("utf-8") == kafka_key:
                    match = True
            if k == 'invokehttp.status.code':
                status_code = v.decode("utf-8")

        if match:
            message_value = msg.value.decode("utf-8")
            try:
                message_value = json.loads(message_value)
            except:
                pass
            resp = jsonify(message_value)
            resp.status_code = status_code
            return resp
    return None

@app.route("/", methods=['PUT'])
def create():
    topic = ""
    if 'topic' in request.args:
        topic = request.args.get("topic")

    if len(topic) == 0:
        # no topic 400 error
        return generate_response(400, {"message": "Topic not found: must include a topic to create (PUT)"})

    consumer = KafkaConsumer(topic, bootstrap_servers=kafkabootstrap,
                             sasl_mechanism="PLAIN", sasl_plain_username=kafkauser, sasl_plain_password=kafkapw,
                             consumer_timeout_ms=2000)

    existingtopics = consumer.topics()

    if topic in existingtopics:

        return generate_response(400, {"message": "Topic already exists: cannot recreate existing topic"})

    admin_client = KafkaAdminClient(
        bootstrap_servers=kafkabootstrap,
        client_id="bootstrapclient"
    )

    topic_list = []
    topic_list.append(NewTopic(name=topic, num_partitions=1, replication_factor=1))
    admin_client.create_topics(new_topics=topic_list, validate_only=False)

    return generate_response(200, {"topic": topic,
                                   "message": "topic created"})

def generate_response(statuscode, otherdata={}):

    message = {
        "status": str(statuscode)
    }
    message.update(otherdata)
    resp = jsonify(message)
    resp.status_code = statuscode
    return resp

if __name__ == '__main__':
   app.run()
