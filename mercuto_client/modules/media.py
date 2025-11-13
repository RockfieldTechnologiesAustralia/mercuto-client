import os
from datetime import timedelta
from typing import TYPE_CHECKING, Literal, Optional

from pydantic import TypeAdapter

if TYPE_CHECKING:
    from ..client import MercutoClient

from datetime import datetime

from ..exceptions import MercutoHTTPException
from . import PayloadType
from ._util import BaseModel


class Image(BaseModel):
    code: str
    project: str
    mime_type: str
    size_bytes: int
    name: str
    access_url: str
    access_expires: datetime
    camera: Optional[str] = None
    timestamp: Optional[datetime] = None
    event: Optional[str] = None


class Video(BaseModel):
    code: str
    project: str
    start_time: datetime
    end_time: datetime

    mime_type: str
    size_bytes: int
    name: str

    access_url: str
    access_expires: datetime

    event: Optional[str] = None
    camera: Optional[str] = None


class _VideoUploadInitializeResponse(BaseModel):
    request_id: str
    presigned_put_url: str
    presigned_url_expires: datetime


class Healthcheck(BaseModel):
    status: str


class CameraTrigger(BaseModel):
    trigger_channel: str
    pre_interval: timedelta = timedelta(seconds=10)
    post_interval: timedelta = timedelta(seconds=10)
    enabled: bool = True
    trigger_greater_than: Optional[float] = None
    trigger_less_than: Optional[float] = None


class Camera(BaseModel):
    code: str
    project: str
    label: str
    triggers: list[CameraTrigger]
    camera_type: Literal['BOSCH', 'DIRECT_RTSP',
                         'STATIC', 'ROCKFIELD-CAMERA-SERVER-VERSION-2']
    encode_timestamp: bool = True
    encode_blur: bool = False
    blur_steps: Optional[int] = None
    blur_sigma: Optional[float] = None
    tunnel_address: Optional[str] = None
    tunnel_port: Optional[int] = None
    tunnel_username: Optional[str] = None
    tunnel_password: Optional[str] = None
    tunnel_key: Optional[str] = None
    camera_ip: Optional[str] = None
    camera_port: Optional[int] = None
    camera_username: Optional[str] = None
    camera_password: Optional[str] = None
    camera_serial: Optional[str] = None
    rtsp_url: Optional[str] = None


# --- TypeAdapters for lists ---
_ImagelistAdapter = TypeAdapter(list[Image])
_VideolistAdapter = TypeAdapter(list[Video])


class MercutoMediaService:
    def __init__(self, client: 'MercutoClient', path: str = '/media') -> None:
        self._client = client
        self._path = path

    def healthcheck(self) -> Healthcheck:
        r = self._client.request(f"{self._path}/healthcheck", "GET")
        return Healthcheck.model_validate_json(r.text)

    # --- Images ---

    def list_images(self, project: str,
                    camera: Optional[str] = None,
                    event: Optional[str] = None,
                    start_time: Optional[datetime] = None,
                    end_time: Optional[datetime] = None,
                    limit: int = 10,
                    offset: int = 0,
                    ascending: bool = True) -> list[Image]:
        params: PayloadType = {
            'project': project,
            'limit': limit,
            'offset': offset,
            'ascending': ascending
        }
        if camera is not None:
            params["camera"] = camera
        if event is not None:
            params["event"] = event
        if start_time is not None:
            if start_time.tzinfo is None:
                raise ValueError("start_time must be timezone-aware")
            params["start_time"] = start_time.isoformat()
        if end_time is not None:
            if end_time.tzinfo is None:
                raise ValueError("end_time must be timezone-aware")
            params["end_time"] = end_time.isoformat()
        r = self._client.request(f"{self._path}/images", "GET", params=params)
        return _ImagelistAdapter.validate_json(r.text)

    def get_image(self, image_code: str) -> Image:
        r = self._client.request(f"{self._path}/images/{image_code}", "GET")
        return Image.model_validate_json(r.text)

    def delete_image(self, image_code: str) -> None:
        self._client.request(f"{self._path}/images/{image_code}", "DELETE")

    def upload_image(self, filename: str, project: str,
                     camera: Optional[str] = None,
                     timestamp: Optional[datetime] = None,
                     event: Optional[str] = None,
                     filedata: Optional[bytes] = None) -> Image:
        """
        Upload an image to the media service.
        Provide either filename (path to file) or filedata (bytes of file) + filename (reference only).
        """
        params: PayloadType = {
            'project': project
        }
        if camera is not None:
            params["camera"] = camera
        if timestamp is not None:
            if timestamp.tzinfo is None:
                raise ValueError("timestamp must be timezone-aware")
            params["timestamp"] = timestamp.isoformat()
        if event is not None:
            params["event"] = event

        if filedata is not None:
            from io import BytesIO
            r = self._client.request(
                f"{self._path}/images", "PUT", params=params, files={'file': (filename, BytesIO(filedata))})
            return Image.model_validate_json(r.text)
        else:
            with open(filename, 'rb') as f:
                r = self._client.request(
                    f"{self._path}/images", "PUT", params=params, files={'file': f})
        return Image.model_validate_json(r.text)

    # --- Videos ---

    def list_videos(self, project: str,
                    camera: Optional[str] = None,
                    event: Optional[str] = None,
                    start_time: Optional[datetime] = None,
                    end_time: Optional[datetime] = None,
                    limit: int = 10,
                    offset: int = 0,
                    ascending: bool = True) -> list[Video]:
        params: PayloadType = {
            'project': project,
            'limit': limit,
            'offset': offset,
            'ascending': ascending
        }
        if camera is not None:
            params["camera"] = camera
        if event is not None:
            params["event"] = event
        if start_time is not None:
            if start_time.tzinfo is None:
                raise ValueError("start_time must be timezone-aware")
            params["start_time"] = start_time.isoformat()
        if end_time is not None:
            if end_time.tzinfo is None:
                raise ValueError("end_time must be timezone-aware")
            params["end_time"] = end_time.isoformat()
        r = self._client.request(f"{self._path}/videos", "GET", params=params)
        return _VideolistAdapter.validate_json(r.text)

    def get_video(self, video_code: str) -> Video:
        r = self._client.request(f"{self._path}/videos/{video_code}", "GET")
        return Video.model_validate_json(r.text)

    def upload_video(self, filename: str, project: str,
                     start_time: datetime,
                     end_time: datetime,
                     camera: Optional[str] = None,
                     event: Optional[str] = None) -> str:
        """
        Upload a video file to the media service.
        This is a multi-step process.
        First, the request is initialized to get an upload URL.
        Then, the file is uploaded to the provided URL.
        Finally, the upload is finalized.

        :returns: A request ID used to track the status of the uploaded video processing. Pass this to the /requests/{request_id} endpoint
        to check the status and get the video_id once processing is complete.
        """
        import mimetypes
        mime_type = mimetypes.guess_type(filename, strict=False)[0]
        if mime_type is None:
            raise ValueError(
                f"Could not determine MIME type for file: {filename}")
        if mime_type not in {'video/mp4', 'video/avi', 'video/mov', 'video/mkv'}:
            raise ValueError(f"Unsupported video MIME type: {mime_type}")

        # 1. Make the initialize upload request
        init_payload: PayloadType = {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'mime_type': mime_type,
            'filename': os.path.basename(filename)
        }
        if camera is not None:
            init_payload['camera'] = camera
        if event is not None:
            init_payload['event'] = event
        init_request = self._client.request(f"{self._path}/videos", "POST", json=init_payload,
                                            params={'project': project, 'action': 'initialize'})
        init_request_response = _VideoUploadInitializeResponse.model_validate_json(
            init_request.text)

        # 2. Upload the video file
        with open(filename, 'rb') as f:
            resp = self._client.session().put(init_request_response.presigned_put_url,
                                              data=f, verify=self._client.verify_ssl)
            if not resp.ok:
                raise MercutoHTTPException(
                    f"Video upload failed: {resp.text}", resp.status_code)

        # 3. Finalize the upload
        self._client.request(f"{self._path}/videos", "POST", params={
            'project': project,
            'action': 'commit',
            'request_id': init_request_response.request_id
        })

        return init_request_response.request_id

    # --- Cameras ---

    def create_camera(self, project: str,
                      label: str,
                      triggers: list[CameraTrigger],
                      encode_timestamp: bool = True,
                      encode_blur: bool = False,
                      blur_steps: Optional[int] = None,
                      blur_sigma: Optional[float] = None,
                      tunnel_address: Optional[str] = None,
                      tunnel_port: Optional[int] = None,
                      tunnel_username: Optional[str] = None,
                      tunnel_password: Optional[str] = None,
                      tunnel_key: Optional[str] = None,
                      camera_ip: Optional[str] = None,
                      camera_port: Optional[int] = None,
                      camera_username: Optional[str] = None,
                      camera_password: Optional[str] = None,
                      camera_serial: Optional[str] = None,
                      camera_type: Literal['BOSCH', 'DIRECT_RTSP', 'STATIC',
                                           'ROCKFIELD-CAMERA-SERVER-VERSION-2'] = 'DIRECT_RTSP',
                      rtsp_url: Optional[str] = None,) -> Camera:
        payload: PayloadType = {
            'label': label,
            'encode_timestamp': encode_timestamp,
            'encode_blur': encode_blur,
        }
        if blur_steps is not None:
            payload['blur_steps'] = blur_steps
        if blur_sigma is not None:
            payload['blur_sigma'] = blur_sigma
        if tunnel_address is not None:
            tunnel_payload: PayloadType = {
                'address': tunnel_address,
                'port': tunnel_port,
                'username': tunnel_username,
                'password': tunnel_password,
                'key': tunnel_key
            }
            payload['ssh_tunnel'] = tunnel_payload
        if camera_ip is not None:
            payload['camera_ip'] = camera_ip
        if camera_port is not None:
            payload['camera_port'] = camera_port
        if camera_username is not None:
            payload['camera_username'] = camera_username
        if camera_password is not None:
            payload['camera_password'] = camera_password
        if camera_serial is not None:
            payload['camera_serial'] = camera_serial
        payload['camera_type'] = camera_type
        if rtsp_url is not None:
            payload['rtsp_url'] = rtsp_url

        if triggers:
            payload['triggers'] = [trigger.model_dump(mode='json') for trigger in triggers]  # type: ignore

        r = self._client.request(
            f"{self._path}/cameras", "PUT", json=payload, params={'project': project})
        return Camera.model_validate_json(r.text)
