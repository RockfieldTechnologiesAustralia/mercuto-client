import logging
import mimetypes
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..client import MercutoClient
from ..exceptions import MercutoHTTPException
from ..modules.media import Image, MercutoMediaService, Video
from ._utility import EnforceOverridesMeta, create_data_url

logger = logging.getLogger(__name__)


class MockMercutoMediaService(MercutoMediaService, metaclass=EnforceOverridesMeta):
    def __init__(self, client: 'MercutoClient'):
        super().__init__(client=client)
        self._events: dict[str, Image] = {}
        self._videos: dict[str, Video] = {}

    def upload_image(self, filename: str, project: str,
                     camera: Optional[str] = None,
                     timestamp: Optional[datetime] = None,
                     event: Optional[str] = None,
                     filedata: Optional[bytes] = None) -> Image:
        code = str(uuid.uuid4())
        mime_type, _ = mimetypes.guess_type(filename, strict=False)
        if mime_type is None:
            raise ValueError("Could not determine MIME type for file")
        if mime_type not in ['image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/tiff']:
            raise MercutoHTTPException(f"Unsupported image MIME type: {mime_type}", 400)
        if filedata is not None:
            data = filedata
        else:
            with open(filename, 'rb') as f:
                data = f.read()
        data_url = create_data_url(mime_type, data)
        image = Image(code=code, project=project, camera=camera, timestamp=timestamp, event=event, access_url=data_url,
                      mime_type=mime_type, access_expires=datetime.now(timezone.utc) + timedelta(days=365),
                      size_bytes=len(data), name=os.path.basename(filename))
        self._events[code] = image
        return image

    def list_images(self, project: str,
                    camera: Optional[str] = None,
                    event: Optional[str] = None,
                    start_time: Optional[datetime] = None,
                    end_time: Optional[datetime] = None,
                    limit: int = 10,
                    offset: int = 0,
                    ascending: bool = True) -> list[Image]:
        results = [img for img in self._events.values() if img.project == project]
        if camera:
            results = [img for img in results if img.camera == camera]
        if event:
            results = [img for img in results if img.event == event]
        if start_time:
            results = [img for img in results if img.timestamp and img.timestamp >= start_time]
        if end_time:
            results = [img for img in results if img.timestamp and img.timestamp <= end_time]
        results.sort(key=lambda img: img.timestamp or datetime.min, reverse=not ascending)
        return results[offset:offset + limit]

    def get_image(self, image_code: str) -> Image:
        try:
            return self._events[image_code]
        except KeyError:
            raise MercutoHTTPException(f"Image not found: {image_code}", 404)

    def delete_image(self, image_code: str) -> None:
        try:
            del self._events[image_code]
        except KeyError:
            raise MercutoHTTPException(f"Image not found: {image_code}", 404)

    def upload_video(self, filename: str, project: str, start_time: datetime, end_time: datetime,
                     camera: str | None = None, event: str | None = None) -> str:
        code = str(uuid.uuid4())
        mime_type, _ = mimetypes.guess_type(filename, strict=False)
        if mime_type is None:
            raise ValueError("Could not determine MIME type for file")
        with open(filename, 'rb') as f:
            data = f.read()
            data_url = create_data_url(mime_type, data)
        video = Video(code=code, project=project, camera=camera, start_time=start_time, end_time=end_time, event=event,
                      access_url=data_url, mime_type=mime_type,
                      access_expires=datetime.now(timezone.utc) + timedelta(days=365),
                      size_bytes=len(data), name=os.path.basename(filename))
        self._videos[code] = video
        return code

    def list_videos(self, project: str,
                    camera: Optional[str] = None,
                    event: Optional[str] = None,
                    start_time: Optional[datetime] = None,
                    end_time: Optional[datetime] = None,
                    limit: int = 10,
                    offset: int = 0,
                    ascending: bool = True) -> list[Video]:
        results = [vid for vid in self._videos.values() if vid.project == project]
        if camera:
            results = [vid for vid in results if vid.camera == camera]
        if event:
            results = [vid for vid in results if vid.event == event]
        if start_time:
            results = [vid for vid in results if vid.start_time and vid.start_time >= start_time]
        if end_time:
            results = [vid for vid in results if vid.end_time and vid.end_time <= end_time]
        results.sort(key=lambda vid: vid.start_time or datetime.min, reverse=not ascending)
        return results[offset:offset + limit]

    def get_video(self, video_code: str) -> Video:
        try:
            return self._videos[video_code]
        except KeyError:
            raise MercutoHTTPException(f"Video not found: {video_code}", 404)
