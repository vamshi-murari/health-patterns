# Copyright 2021 IBM All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Testcases related to enriching fhir resources"""
# pylint: disable=missing-function-docstring
import importlib


from fhir.resources.bundle import Bundle

from test_text_analytics.util.compare import compare_actual_to_expected
from test_text_analytics.util.fhir import (
    make_condition,
    make_codeable_concept,
    make_bundle,
    make_patient_reference,
    make_allergy_intolerance,
    make_allergy_reaction,
    make_immunization,
)
from test_text_analytics.util.mock_service import (
    make_mock_acd_service_class,
    configure_acd,
    make_mock_quick_umls_service_class,
    configure_quick_umls,
)
from test_text_analytics.util.resources import UnitTestUsingExternalResource
from text_analytics import app


class TestEnrichUsingAcd(UnitTestUsingExternalResource):
    """Unit tests where a diagnostic report is posted for insights"""

    def setUp(self) -> None:
        # The application is defined globally in the module, so this is a potentially
        # flawed way of reseting the state between test cases.
        # It should work "well-enough" in most cases.
        importlib.reload(app)
        app.all_nlp_services["acd"] = make_mock_acd_service_class(
            self.resource_path + "/acd/TestEnrichResponses.json"
        )

    def test_when_post_condition_bundle_then_condition_enriched(self):

        bundle = make_bundle(
            [
                make_condition(
                    subject=make_patient_reference(),
                    code=make_codeable_concept(text="Heart Attack"),
                )
            ]
        )

        with app.app.test_client() as service:
            configure_acd(service)
            insight_resp = service.post("/discoverInsights", json=bundle.dict())
            self.assertEqual(200, insight_resp.status_code)

            actual_bundle = Bundle.parse_obj(insight_resp.get_json())
            cmp = compare_actual_to_expected(
                expected_path=self.expected_output_path(),
                actual_resource=actual_bundle,
            )
            self.assertFalse(cmp, cmp.pretty())

    def test_when_post_allergy_intolerance_bundle_then_intolerance_enriched(self):
        bundle = make_bundle(
            [
                make_allergy_intolerance(
                    patient=make_patient_reference(),
                    code=make_codeable_concept(text="Oxycodone"),
                    reactions=[
                        make_allergy_reaction(
                            manifestations=[
                                make_codeable_concept(text="Muscle Pain"),
                                make_codeable_concept(text="hair loss"),
                            ]
                        )
                    ],
                )
            ]
        )

        with app.app.test_client() as service:
            configure_acd(service)
            insight_resp = service.post("/discoverInsights", json=bundle.dict())
            self.assertEqual(200, insight_resp.status_code)

            actual_bundle = Bundle.parse_obj(insight_resp.get_json())
            cmp = compare_actual_to_expected(
                expected_path=self.expected_output_path(),
                actual_resource=actual_bundle,
            )
            self.assertFalse(cmp, cmp.pretty())

    def test_when_post_immunization_bundle_then_immunization_enriched(self):
        bundle = make_bundle(
            [
                make_immunization(
                    patient=make_patient_reference(),
                    vaccine_code=make_codeable_concept(text="DTaP"),
                )
            ]
        )

        with app.app.test_client() as service:
            configure_acd(service)
            insight_resp = service.post("/discoverInsights", json=bundle.dict())
            self.assertEqual(200, insight_resp.status_code, insight_resp.data)

            actual_bundle = Bundle.parse_obj(insight_resp.get_json())
            cmp = compare_actual_to_expected(
                expected_path=self.expected_output_path(),
                actual_resource=actual_bundle,
            )
            self.assertFalse(cmp, cmp.pretty())


class TestEnrichUsingQuickUmls(UnitTestUsingExternalResource):
    """Unit tests where a diagnostic report is posted for insights"""

    def setUp(self) -> None:
        # The application is defined globally in the module, so this is a potentially
        # flawed way of reseting the state between test cases.
        # It should work "well-enough" in most cases.
        importlib.reload(app)
        app.all_nlp_services["quickumls"] = make_mock_quick_umls_service_class(
            self.resource_path + "/quickUmls/TestEnrichResponses.json"
        )

    def test_when_post_condition_bundle_then_condition_enriched(self):

        bundle = make_bundle(
            [
                make_condition(
                    subject=make_patient_reference(),
                    code=make_codeable_concept(text="Heart Attack"),
                )
            ]
        )

        with app.app.test_client() as service:
            configure_quick_umls(service)
            insight_resp = service.post("/discoverInsights", json=bundle.dict())
            self.assertEqual(200, insight_resp.status_code)

            actual_bundle = Bundle.parse_obj(insight_resp.get_json())
            cmp = compare_actual_to_expected(
                expected_path=self.expected_output_path(),
                actual_resource=actual_bundle,
            )
            self.assertFalse(cmp, cmp.pretty())

    def test_when_post_allergy_intolerance_bundle_then_intolerance_enriched(self):
        bundle = make_bundle(
            [
                make_allergy_intolerance(
                    patient=make_patient_reference(),
                    code=make_codeable_concept(text="Oxycodone"),
                    reactions=[
                        make_allergy_reaction(
                            manifestations=[
                                make_codeable_concept(text="Muscle Pain"),
                                make_codeable_concept(text="hair loss"),
                            ]
                        )
                    ],
                )
            ]
        )

        with app.app.test_client() as service:
            configure_quick_umls(service)
            insight_resp = service.post("/discoverInsights", json=bundle.dict())
            self.assertEqual(200, insight_resp.status_code)

            actual_bundle = Bundle.parse_obj(insight_resp.get_json())
            cmp = compare_actual_to_expected(
                expected_path=self.expected_output_path(),
                actual_resource=actual_bundle,
            )
            self.assertFalse(cmp, cmp.pretty())

    def test_when_post_immunization_bundle_then_immunization_enriched(self):
        bundle = make_bundle(
            [
                make_immunization(
                    patient=make_patient_reference(),
                    vaccine_code=make_codeable_concept(text="DTaP"),
                )
            ]
        )

        with app.app.test_client() as service:
            configure_quick_umls(service)
            insight_resp = service.post("/discoverInsights", json=bundle.dict())
            self.assertEqual(200, insight_resp.status_code, insight_resp.data)

            actual_bundle = Bundle.parse_obj(insight_resp.get_json())
            cmp = compare_actual_to_expected(
                expected_path=self.expected_output_path(),
                actual_resource=actual_bundle,
            )
            self.assertFalse(cmp, cmp.pretty())