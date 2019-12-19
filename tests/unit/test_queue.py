import json
import os
from types import SimpleNamespace

import pytest
from mock import patch, ANY


with patch.dict(os.environ, {"DeletionQueueTable": "DeletionQueueTable"}):
    from backend.lambdas.queue import handlers

pytestmark = [pytest.mark.unit, pytest.mark.api, pytest.mark.queue]


@patch("backend.lambdas.queue.handlers.table")
def test_it_retrieves_all_items(table):
    table.scan.return_value = {"Items": []}
    response = handlers.get_handler({}, SimpleNamespace())
    assert {
        "statusCode": 200,
        "body": json.dumps({"MatchIds": []}),
        "headers": ANY
    } == response


@patch("backend.lambdas.queue.handlers.table")
def test_it_add_to_queue(table):
    response = handlers.enqueue_handler({
        "body": json.dumps({
            "MatchId": "test",
            "DataMappers": ["a"],
        })
    }, SimpleNamespace())

    assert 201 == response["statusCode"]
    assert {
        "MatchId": "test",
        "DataMappers": ["a"],
    } == json.loads(response["body"])


@patch("backend.lambdas.queue.handlers.table")
def test_it_provides_default_data_mappers(table):
    response = handlers.enqueue_handler({
        "body": json.dumps({
            "MatchId": "test"
        })
    }, SimpleNamespace())

    assert 201 == response["statusCode"]
    assert {
        "MatchId": "test",
        "DataMappers": [],
    } == json.loads(response["body"])


@patch("backend.lambdas.queue.handlers.table")
def test_it_cancels_deletions(table):
    response = handlers.cancel_handler({
        "pathParameters": {
            "match_id": "test",
        }
    }, SimpleNamespace())
    assert {
        "statusCode": 204,
        "headers": ANY
    } == response


@patch("backend.lambdas.queue.handlers.sfn_client")
def test_it_process_queue(sfn_client):
    sfn_client.start_execution.return_value = {
        "executionArn": "arn:aws:states:eu-west-1:123456789012:execution:HelloWorld:e723c10b-9be4-46ca-90b8-8b94a7105b44",
        "startDate": 1571321214.368
    }
    response = handlers.process_handler({
        "body": ""
    }, SimpleNamespace())
    assert {
        "statusCode": 202,
        "body": json.dumps({
            "JobId": "e723c10b-9be4-46ca-90b8-8b94a7105b44"
        }),
        "headers": ANY
    } == response
