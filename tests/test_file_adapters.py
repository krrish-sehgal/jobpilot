"""S3, SQS and document adapters, exercised with client doubles (no network)."""

from io import BytesIO

import pytest
from botocore.exceptions import ClientError

from jobpilot.config import Settings
from jobpilot.errors import ObjectStorageError, ResumeParseError
from jobpilot.integrations.queue_backend import SqsQueueBackend
from jobpilot.integrations.storage import S3ObjectStorage
from jobpilot.resume.extract import DocumentTextExtractor, FileKind
from jobpilot.resume.render import DocumentFormat, FileDocumentRenderer
from tests.resume_fixtures import sample_sections


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "op")


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, *, Bucket, Key, Body):
        self.objects[(Bucket, Key)] = Body

    def get_object(self, *, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise _client_error("NoSuchKey")
        return {"Body": BytesIO(self.objects[(Bucket, Key)])}

    def head_object(self, *, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise _client_error("404")

    def delete_object(self, *, Bucket, Key):
        self.objects.pop((Bucket, Key), None)


def test_s3_storage_round_trip_and_missing_keys():
    storage = S3ObjectStorage(Settings(object_storage_bucket="b"), client=FakeS3())
    storage.put("k", b"data")
    assert storage.exists("k") and storage.get("k") == b"data"
    storage.delete("k")
    assert not storage.exists("k")
    with pytest.raises(ObjectStorageError, match="no object"):
        storage.get("k")


def test_s3_storage_requires_credentials_without_an_injected_client():
    with pytest.raises(ObjectStorageError, match="credentials"):
        S3ObjectStorage(Settings())


class FakeSqs:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def send_message(self, **kwargs):
        self.calls.append(("send", kwargs))
        return {"MessageId": "m-1"}

    def receive_message(self, **kwargs):
        self.calls.append(("receive", kwargs))
        return {
            "Messages": [
                {
                    "ReceiptHandle": "rh-1",
                    "Body": "{}",
                    "Attributes": {"ApproximateReceiveCount": "2"},
                }
            ]
        }

    def delete_message(self, **kwargs):
        self.calls.append(("delete", kwargs))

    def get_queue_attributes(self, **kwargs):
        return {"Attributes": {"ApproximateNumberOfMessages": "7"}}


def test_sqs_backend_maps_messages_and_receipt_handles():
    queue = SqsQueueBackend(Settings(queue_url="https://sqs.test/q"), client=FakeSqs())
    assert queue.send("{}") == "m-1"
    [message] = queue.receive(max_messages=50)
    assert (message.id, message.body, message.receive_count) == ("rh-1", "{}", 2)
    queue.delete(message.id)
    assert queue.queue_depth() == 7
    calls = dict((name, kwargs) for name, kwargs in queue._client.calls)
    assert calls["receive"]["MaxNumberOfMessages"] == 10
    assert calls["delete"]["ReceiptHandle"] == "rh-1"


def test_docx_renderer_and_extractor_round_trip():
    rendered = FileDocumentRenderer().render(sample_sections(), DocumentFormat.DOCX)
    assert rendered.extension == "docx"
    text = DocumentTextExtractor().extract(rendered.content, FileKind.DOCX)
    assert text.splitlines()[0] == "Priya Nair"
    assert "Experience" in text


def test_extractor_rejects_unreadable_files():
    with pytest.raises(ResumeParseError):
        DocumentTextExtractor().extract(b"PK\x03\x04 not a real archive", FileKind.DOCX)
    with pytest.raises(ResumeParseError):
        DocumentTextExtractor().extract(b"%PDF-1.4 truncated", FileKind.PDF)
