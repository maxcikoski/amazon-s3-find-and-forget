import os
import re
from types import SimpleNamespace

import pytest
from mock import patch

from backend.lambdas.tasks.execute_query import handler, make_query, escape_item

pytestmark = [pytest.mark.unit, pytest.mark.task]


def escape_resp(resp):
    return re.sub("[\x00-\x20]+", " ", resp.strip())


@patch("backend.lambdas.tasks.execute_query.client")
@patch("backend.lambdas.tasks.execute_query.make_query")
def test_it_executes_queries(query_mock, client_mock):
    client_mock.start_query_execution.return_value = {"QueryExecutionId": "123"}
    query_mock.return_value = "test"

    resp = handler(
        {"QueryData": {}, "Bucket": "mybucket", "Prefix": "my_prefix"},
        SimpleNamespace(),
    )
    assert "123" == resp
    client_mock.start_query_execution.assert_called_with(
        QueryString="test",
        ResultConfiguration={"OutputLocation": "s3://mybucket/my_prefix/"},
        WorkGroup="primary",
    )


@patch("backend.lambdas.tasks.execute_query.client")
@patch("backend.lambdas.tasks.execute_query.make_query")
def test_it_permits_custom_workgroups(query_mock, client_mock):
    client_mock.start_query_execution.return_value = {"QueryExecutionId": "123"}
    query_mock.return_value = "test"
    with patch.dict(os.environ, {"WorkGroup": "custom"}):
        resp = handler(
            {"QueryData": {}, "Bucket": "mybucket", "Prefix": "my_prefix"},
            SimpleNamespace(),
        )
    assert "123" == resp
    client_mock.start_query_execution.assert_called_with(
        QueryString="test",
        ResultConfiguration={"OutputLocation": "s3://mybucket/my_prefix/"},
        WorkGroup="custom",
    )


def test_it_generates_query_with_partition():
    resp = make_query(
        {
            "Database": "amazonreviews",
            "Table": "amazon_reviews_parquet",
            "Columns": [
                {
                    "Column": "customer_id",
                    "MatchIds": ["123456", "456789"],
                    "Type": "Simple",
                }
            ],
            "PartitionKeys": [{"Key": "product_category", "Value": "Books"}],
        }
    )

    assert (
        escape_resp(resp) == 'SELECT DISTINCT "$path" '
        'FROM "amazonreviews"."amazon_reviews_parquet" '
        "WHERE (\"customer_id\" in ('123456', '456789')) "
        "AND \"product_category\" = 'Books'"
    )


def test_it_generates_query_with_partition_and_int_column():
    resp = make_query(
        {
            "Database": "amazonreviews",
            "Table": "amazon_reviews_parquet",
            "Columns": [
                {
                    "Column": "customer_id",
                    "MatchIds": [123456, 456789],
                    "Type": "Simple",
                }
            ],
            "PartitionKeys": [{"Key": "product_category", "Value": "Books"}],
        }
    )

    assert (
        escape_resp(resp) == 'SELECT DISTINCT "$path" '
        'FROM "amazonreviews"."amazon_reviews_parquet" '
        'WHERE ("customer_id" in (123456, 456789)) '
        "AND \"product_category\" = 'Books'"
    )


def test_it_generates_query_with_int_partition():
    resp = make_query(
        {
            "Database": "amazonreviews",
            "Table": "amazon_reviews_parquet",
            "Columns": [
                {
                    "Column": "customer_id",
                    "MatchIds": ["123456", "456789"],
                    "Type": "Simple",
                }
            ],
            "PartitionKeys": [{"Key": "year", "Value": 2010}],
        }
    )

    assert (
        escape_resp(resp) == 'SELECT DISTINCT "$path" '
        'FROM "amazonreviews"."amazon_reviews_parquet" '
        "WHERE (\"customer_id\" in ('123456', '456789')) "
        'AND "year" = 2010'
    )


def test_it_generates_query_with_multiple_partitions():
    resp = make_query(
        {
            "Database": "amazonreviews",
            "Table": "amazon_reviews_parquet",
            "Columns": [
                {
                    "Column": "customer_id",
                    "MatchIds": ["123456", "456789"],
                    "Type": "Simple",
                }
            ],
            "PartitionKeys": [
                {"Key": "product_category", "Value": "Books"},
                {"Key": "published", "Value": "2019"},
            ],
        }
    )

    assert (
        escape_resp(resp) == 'SELECT DISTINCT "$path" '
        'FROM "amazonreviews"."amazon_reviews_parquet" '
        "WHERE (\"customer_id\" in ('123456', '456789')) "
        "AND \"product_category\" = 'Books' "
        "AND \"published\" = '2019'"
    )


def test_it_generates_query_without_partition():
    resp = make_query(
        {
            "Database": "amazonreviews",
            "Table": "amazon_reviews_parquet",
            "Columns": [
                {
                    "Column": "customer_id",
                    "MatchIds": ["123456", "456789"],
                    "Type": "Simple",
                }
            ],
        }
    )

    assert (
        escape_resp(resp) == 'SELECT DISTINCT "$path" '
        'FROM "amazonreviews"."amazon_reviews_parquet" '
        "WHERE (\"customer_id\" in ('123456', '456789'))"
    )


def test_it_generates_query_with_multiple_columns():
    resp = make_query(
        {
            "Database": "amazonreviews",
            "Table": "amazon_reviews_parquet",
            "Columns": [
                {"Column": "a", "MatchIds": ["a123456", "b123456"], "Type": "Simple"},
                {"Column": "b", "MatchIds": ["a456789", "b456789"], "Type": "Simple"},
            ],
        }
    )

    assert (
        escape_resp(resp) == 'SELECT DISTINCT "$path" '
        'FROM "amazonreviews"."amazon_reviews_parquet" '
        "WHERE (\"a\" in ('a123456', 'b123456') OR \"b\" in ('a456789', 'b456789'))"
    )


def test_it_generates_query_with_columns_of_complex_type():
    resp = make_query(
        {
            "Database": "amazonreviews",
            "Table": "amazon_reviews_parquet",
            "Columns": [
                {
                    "Column": "a.b.c",
                    "MatchIds": ["a123456", "b123456"],
                    "Type": "Simple",
                }
            ],
        }
    )

    assert (
        escape_resp(resp) == 'SELECT DISTINCT "$path" '
        'FROM "amazonreviews"."amazon_reviews_parquet" '
        'WHERE ("a"."b"."c" in (\'a123456\', \'b123456\'))'
    )


def test_it_generates_query_with_composite_matches():
    resp = make_query(
        {
            "Database": "amazonreviews",
            "Table": "amazon_reviews_parquet",
            "Columns": [
                {
                    "Columns": ["user.first_name", "user.last_name"],
                    "MatchIds": [["John", "Doe"], ["Jane", "Doe"]],
                    "Type": "Composite",
                },
                {
                    "Columns": ["user.age", "user.last_name"],
                    "MatchIds": [[28, "Smith"]],
                    "Type": "Composite",
                },
                {
                    "Columns": ["user.userid"],
                    "MatchIds": [["123456"]],
                    "Type": "Composite",
                },
            ],
        }
    )

    assert (
        escape_resp(resp) == 'SELECT DISTINCT "$path" '
        'FROM "amazonreviews"."amazon_reviews_parquet" '
        'WHERE (concat("user"."first_name", \'_S3F2COMP_\', "user"."last_name") '
        "in ('John_S3F2COMP_Doe', 'Jane_S3F2COMP_Doe') OR "
        'concat("user"."age", \'_S3F2COMP_\', "user"."last_name") '
        "in ('28_S3F2COMP_Smith') OR "
        '"user"."userid" in (\'123456\'))'
    )


def test_it_generates_query_with_simple_and_composite_matches():
    resp = make_query(
        {
            "Database": "amazonreviews",
            "Table": "amazon_reviews_parquet",
            "Columns": [
                {
                    "Column": "a.b.c",
                    "MatchIds": ["a123456", "b123456"],
                    "Type": "Simple",
                },
                {
                    "Columns": ["user.first_name", "user.last_name"],
                    "MatchIds": [["John", "Doe"], ["Jane", "Doe"]],
                    "Type": "Composite",
                },
            ],
        }
    )

    assert (
        escape_resp(resp) == 'SELECT DISTINCT "$path" '
        'FROM "amazonreviews"."amazon_reviews_parquet" '
        'WHERE ("a"."b"."c" in (\'a123456\', \'b123456\') '
        'OR concat("user"."first_name", \'_S3F2COMP_\', "user"."last_name") '
        "in ('John_S3F2COMP_Doe', 'Jane_S3F2COMP_Doe'))"
    )


def test_it_escapes_strings():
    assert "''' OR 1=1'" == escape_item("' OR 1=1")


def test_it_escapes_ints():
    assert 2 == escape_item(2)


def test_it_escapes_floats():
    assert float(2) == escape_item(float(2))


def test_it_escapes_none():
    assert "NULL" == escape_item(None)


def test_it_raises_for_unsupported_type():
    with pytest.raises(ValueError):
        escape_item(["val"])
