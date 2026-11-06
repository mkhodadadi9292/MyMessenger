from enum import Enum

class FileKind(str, Enum):
    FILE = "file"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
