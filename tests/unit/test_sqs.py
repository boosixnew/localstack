import pytest

import localstack.services.sqs.exceptions
import localstack.services.sqs.models
from localstack.services.sqs import provider
from localstack.services.sqs.constants import DEFAULT_MAXIMUM_MESSAGE_SIZE
from localstack.services.sqs.utils import (
    is_sqs_queue_url,
    parse_queue_url,
)
from localstack.services.sqs.provider import _create_message_attribute_hash
from localstack.utils.common import convert_to_printable_chars


def test_sqs_message_attrs_md5():
    msg_attrs = {
        "MessageAttribute.1.Name": "timestamp",
        "MessageAttribute.1.Value.StringValue": "1493147359900",
        "MessageAttribute.1.Value.DataType": "Number",
    }
    md5 = _create_message_attribute_hash(msg_attrs)
    assert md5 == "235c5c510d26fb653d073faed50ae77c"


def test_convert_non_printable_chars():
    string = "invalid characters - %s %s %s" % (chr(8), chr(11), chr(12))
    result = convert_to_printable_chars(string)
    assert result == "invalid characters -   "
    result = convert_to_printable_chars({"foo": [string]})
    assert result == {"foo": ["invalid characters -   "]}

    string = "valid characters - %s %s %s %s" % (chr(9), chr(10), chr(13), chr(32))
    result = convert_to_printable_chars(string)
    assert result == string


def test_compare_sqs_message_attrs_md5():
    msg_attrs_listener = {
        "MessageAttribute.1.Name": "timestamp",
        "MessageAttribute.1.Value.StringValue": "1493147359900",
        "MessageAttribute.1.Value.DataType": "Number",
    }
    md5_listener = get_message_attributes_md5(msg_attrs_listener)
    msg_attrs_provider = {"timestamp": {"StringValue": "1493147359900", "DataType": "Number"}}
    md5_provider = provider._create_message_attribute_hash(msg_attrs_provider)
    assert md5_provider == md5_listener


def test_parse_max_receive_count_string_in_redrive_policy():
    # fmt: off
    policy = {"RedrivePolicy": "{\"deadLetterTargetArn\":\"arn:aws:sqs:us-east-1:000000000000:DeadLetterQueue\",\"maxReceiveCount\": \"5\" }"}
    # fmt: on
    queue = localstack.services.sqs.models.SqsQueue("TestQueue", "us-east-1", "123456789", policy)
    assert queue.max_receive_count == 5


def test_except_check_message_size():
    message_attributes = {"k": {"DataType": "String", "StringValue": "x"}}
    message_attributes_size = len("k") + len("String") + len("x")
    message_body = "a" * (DEFAULT_MAXIMUM_MESSAGE_SIZE - message_attributes_size + 1)
    with pytest.raises(localstack.services.sqs.exceptions.InvalidParameterValueException):
        provider.check_message_size(message_body, message_attributes, DEFAULT_MAXIMUM_MESSAGE_SIZE)


def test_check_message_size():
    message_body = "a"
    message_attributes = {"k": {"DataType": "String", "StringValue": "x"}}
    provider.check_message_size(message_body, message_attributes, DEFAULT_MAXIMUM_MESSAGE_SIZE)


def test_parse_queue_url_valid():
    assert parse_queue_url("http://localhost:4566/queue/eu-central-2/000000000001/my-queue") == (
        "000000000001",
        "eu-central-2",
        "my-queue",
    )
    assert parse_queue_url("http://localhost:4566/000000000001/my-queue") == (
        "000000000001",
        None,
        "my-queue",
    )
    assert parse_queue_url("http://localhost/000000000001/my-queue") == (
        "000000000001",
        None,
        "my-queue",
    )

    assert parse_queue_url("http://localhost/queue/eu-central-2/000000000001/my-queue") == (
        "000000000001",
        "eu-central-2",
        "my-queue",
    )

    assert parse_queue_url(
        "http://queue.localhost.localstack.cloud:4566/000000000001/my-queue"
    ) == (
        "000000000001",
        "us-east-1",
        "my-queue",
    )

    assert parse_queue_url(
        "http://eu-central-2.queue.localhost.localstack.cloud:4566/000000000001/my-queue"
    ) == (
        "000000000001",
        "eu-central-2",
        "my-queue",
    )

    # in this case, eu-central-2.foobar... is treated as a regular hostname
    assert parse_queue_url(
        "http://eu-central-2.foobar.localhost.localstack.cloud:4566/000000000001/my-queue"
    ) == (
        "000000000001",
        None,
        "my-queue",
    )


def test_parse_queue_url_invalid():
    with pytest.raises(ValueError):
        parse_queue_url("http://localhost:4566/my-queue")

    with pytest.raises(ValueError):
        parse_queue_url("http://localhost:4566/eu-central-1/000000000001/my-queue")

    with pytest.raises(ValueError):
        parse_queue_url("http://localhost:4566/foobar/eu-central-1/000000000001/my-queue")

    with pytest.raises(ValueError):
        parse_queue_url(
            "http://eu-central-2.queue.localhost.localstack.cloud:4566/000000000001/my-queue/foobar"
        )

    with pytest.raises(ValueError):
        parse_queue_url(
            "http://queue.localhost.localstack.cloud:4566/us-east-1/000000000001/my-queue"
        )

    with pytest.raises(ValueError):
        assert parse_queue_url("queue.localhost.localstack.cloud:4566/000000000001/my-queue")

    with pytest.raises(ValueError):
        assert parse_queue_url(
            "http://foo.bar.queue.localhost.localstack.cloud:4566/000000000001/my-queue"
        )


def test_is_sqs_queue_url():
    # General cases
    assert is_sqs_queue_url("http://localstack.cloud") is False
    assert is_sqs_queue_url("https://localstack.cloud:4566") is False
    assert is_sqs_queue_url("local.localstack.cloud:4566") is False

    # Without proto prefix
    assert (
        is_sqs_queue_url("sqs.us-east-1.localhost.localstack.cloud:4566/111111111111/foo") is True
    )
    assert (
        is_sqs_queue_url("us-east-1.queue.localhost.localstack.cloud:4566/111111111111/foo") is True
    )
    assert is_sqs_queue_url("localhost:4566/queue/ap-south-1/222222222222/bar") is True
    assert is_sqs_queue_url("localhost:4566/111111111111/bar") is True

    # With proto prefix
    assert (
        is_sqs_queue_url(
            "http://sqs.us-east-1.localhost.localstack.cloud:4566/111111111111/foo.fifo"
        )
        is True
    )
    assert (
        is_sqs_queue_url("http://us-east-1.queue.localhost.localstack.cloud:4566/111111111111/foo1")
        is True
    )
    assert is_sqs_queue_url("http://localhost:4566/queue/ap-south-1/222222222222/my-queue") is True
    assert is_sqs_queue_url("http://localhost:4566/111111111111/bar") is True

    # Path strategy uses any domain name
    assert is_sqs_queue_url("foo.bar:4566/queue/ap-south-1/222222222222/bar") is True
    # Domain strategy may omit region
    assert is_sqs_queue_url("http://queue.localhost.localstack.cloud:4566/111111111111/foo") is True

    # Custom domain name
    assert is_sqs_queue_url("http://foo.bar:4566/queue/us-east-1/111111111111/foo") is True
    assert is_sqs_queue_url("http://us-east-1.queue.foo.bar:4566/111111111111/foo") is True
    assert is_sqs_queue_url("http://queue.foo.bar:4566/111111111111/foo") is True
    assert is_sqs_queue_url("http://sqs.us-east-1.foo.bar:4566/111111111111/foo") is True
