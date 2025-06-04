from CachePath import *
from datetime import datetime
import json
import os
import os.path
from PIL import Image, TiffImagePlugin
from PIL.ExifTags import TAGS
import gc
import html

class Album:
    def __init__(self, path):
        self._path = trim_base(path)
        self._photos = list()
        self._albums = list()
        self._photos_sorted = True
        self._albums_sorted = True

    @property
    def photos(self):
        return self._photos

    @property
    def albums(self):
        return self._albums

    @property
    def path(self):
        return self._path

    def __str__(self):
        return self.path

    @property
    def cache_path(self):
        return json_cache(self.path)

    @property
    def date(self):
        self._sort()
        if len(self._photos) == 0 and len(self._albums) == 0:
            return datetime(1900, 1, 1)
        elif len(self._photos) == 0:
            return self._albums[-1].date
        elif len(self._albums) == 0:
            return self._photos[-1].date
        return max(self._photos[-1].date, self._albums[-1].date)

    def __lt__(self, other):
        return self.date < other.date

    def add_photo(self, photo):
        self._photos.append(photo)
        self._photos_sorted = False

    def add_album(self, album):
        self._albums.append(album)
        self._albums_sorted = False

    def _sort(self):
        if not self._photos_sorted:
            self._photos.sort()
            self._photos_sorted = True
        if not self._albums_sorted:
            self._albums.sort(reverse=True)
            self._albums_sorted = True

    @property
    def empty(self):
        if len(self._photos) != 0:
            return False
        if len(self._albums) == 0:
            return True
        for album in self._albums:
            if not album.empty:
                return False
        return True

    def cache(self, base_dir):
        self._sort()
        with open(os.path.join(base_dir, self.cache_path), 'w') as fp:
            json.dump(self, fp, cls=PhotoAlbumEncoder)

    @staticmethod
    def from_cache(path):
        with open(path, "r") as fp:
            dictionary = json.load(fp)
        return Album.from_dict(dictionary)

    @staticmethod
    def from_dict(dictionary, cripple=True):
        album = Album(dictionary["path"])
        for photo in dictionary["photos"]:
            album.add_photo(Photo.from_dict(photo, untrim_base(album.path)))
        if not cripple:
            for subalbum in dictionary["albums"]:
                album.add_album(Album.from_dict(subalbum), cripple)
        album._sort()
        return album

    def to_dict(self, cripple=True):
        self._sort()
        subalbums = []
        if cripple:
            for sub in self._albums:
                if not sub.empty:
                    subalbums.append({"path": trim_base_custom(sub.path, self._path), "date": sub.date})
        else:
            for sub in self._albums:
                if not sub.empty:
                    subalbums.append(sub)
        return {"path": self.path, "date": self.date, "albums": subalbums, "photos": self._photos}

    def photo_from_path(self, path):
        for photo in self._photos:
            if trim_base(path) == photo._path:
                return photo
        return None


class Photo:
    thumb_sizes = [(75, True), (150, True), (640, False), (800, False), (1024, False)]

    def __init__(self, path, thumb_path=None, attributes=None):
        self._path = trim_base(path)
        self.is_valid = True
        try:
            mtime = file_mtime(path)
        except KeyboardInterrupt:
            raise
        except Exception:
            self.is_valid = False
            return
        if attributes is not None and attributes["dateTimeFile"] >= mtime:
            self._attributes = attributes
            return
        self._attributes = {}
        self._attributes["dateTimeFile"] = mtime

        try:
            image = Image.open(path)
        except KeyboardInterrupt:
            raise
        except Exception:
            self.is_valid = False
            return
        self._metadata(image)
        self._thumbnails(image, thumb_path, path)

    def _metadata(self, image):
        self._attributes["size"] = image.size
        self._orientation = 1
        try:
            info = image._getexif()
        except KeyboardInterrupt:
            raise
        except Exception:
            print(f"\033[91m Warning: picture {self.path} doesn't have any EXIF data \033[0m")
            return
        if not info:
            print(f"\033[91m Warning: picture {self.path} doesn't have any EXIF data \033[0m")
            return

        exif = {}
        for tag, value in info.items():
            decoded = TAGS.get(tag, tag)
            if isinstance(value, (tuple, list)) and isinstance(decoded, str) and decoded.startswith("DateTime") and len(value) >= 1:
                value = value[0]
            if isinstance(value, str):
                value = value.strip().partition("\x00")[0]
                if decoded.startswith("DateTime"):
                    try:
                        value = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                    except KeyboardInterrupt:
                        raise
                    except Exception:
                        continue
            exif[decoded] = value

        if "Artist" in exif:
            self._attributes["artist"] = html.escape(exif["Artist"])
        else:
            print(f"\033[91m Warning: picture {self.path} doesn't have any Artist in EXIF data \033[0m")
        if "Copyright" in exif:
            self._attributes["copyright"] = html.escape(exif["Copyright"])
        else:
            print(f"\033[91m Warning: picture {self.path} doesn't have any Copyright in EXIF data \033[0m")

        if "Orientation" in exif:
            self._orientation = exif["Orientation"]
            if self._orientation in range(5, 9):
                self._attributes["size"] = (self._attributes["size"][1], self._attributes["size"][0])
            if self._orientation - 1 < len(self._metadata_orientation_list):
                self._attributes["orientation"] = self._metadata_orientation_list[self._orientation - 1]
        if "Make" in exif:
            self._attributes["make"] = exif["Make"]
        if "Model" in exif:
            self._attributes["model"] = exif["Model"]
        if "ApertureValue" in exif:
            self._attributes["aperture"] = exif["ApertureValue"]
        elif "FNumber" in exif:
            self._attributes["aperture"] = exif["FNumber"]
        if "FocalLength" in exif:
            self._attributes["focalLength"] = exif["FocalLength"]
        if "ISOSpeedRatings" in exif:
            self._attributes["iso"] = exif["ISOSpeedRatings"]
        if "ISO" in exif:
            self._attributes["iso"] = exif["ISO"]
        if "PhotographicSensitivity" in exif:
            self._attributes["iso"] = exif["PhotographicSensitivity"]
        if "ExposureTime" in exif:
            self._attributes["exposureTime"] = exif["ExposureTime"]
        if "Flash" in exif and exif["Flash"] in self._metadata_flash_dictionary:
            try:
                self._attributes["flash"] = self._metadata_flash_dictionary[exif["Flash"]]
            except KeyboardInterrupt:
                raise
            except Exception:
                pass
        if "LightSource" in exif and exif["LightSource"] in self._metadata_light_source_dictionary:
            try:
                self._attributes["lightSource"] = self._metadata_light_source_dictionary[exif["LightSource"]]
            except KeyboardInterrupt:
                raise
            except Exception:
                pass
        if "ExposureProgram" in exif and exif["ExposureProgram"] < len(self._metadata_exposure_list):
            self._attributes["exposureProgram"] = self._metadata_exposure_list[exif["ExposureProgram"]]
        if "SpectralSensitivity" in exif:
            self._attributes["spectralSensitivity"] = exif["SpectralSensitivity"]
        if "MeteringMode" in exif and exif["MeteringMode"] < len(self._metadata_metering_list):
            self._attributes["meteringMode"] = self._metadata_metering_list[exif["MeteringMode"]]
        if "SensingMethod" in exif and exif["SensingMethod"] < len(self._metadata_sensing_method_list):
            self._attributes["sensingMethod"] = self._metadata_sensing_method_list[exif["SensingMethod"]]
        if "SceneCaptureType" in exif and exif["SceneCaptureType"] < len(self._metadata_scene_capture_type_list):
            self._attributes["sceneCaptureType"] = self._metadata_scene_capture_type_list[exif["SceneCaptureType"]]
        if "SubjectDistanceRange" in exif and exif["SubjectDistanceRange"] < len(self._metadata_subject_distance_range_list):
            self._attributes["subjectDistanceRange"] = self._metadata_subject_distance_range_list[exif["SubjectDistanceRange"]]
        if "ExposureCompensation" in exif:
            self._attributes["exposureCompensation"] = exif["ExposureCompensation"]
        if "ExposureBiasValue" in exif:
            self._attributes["exposureCompensation"] = exif["ExposureBiasValue"]
        if "DateTimeOriginal" in exif:
            self._attributes["dateTimeOriginal"] = exif["DateTimeOriginal"]
        if "DateTime" in exif:
            self._attributes["dateTime"] = exif["DateTime"]

    _metadata_flash_dictionary = {
    0x0: "No Flash", 0x1: "Fired", 0x5: "Fired, Return not detected", 0x7: "Fired, Return detected",
    0x8: "On, Did not fire", 0x9: "On, Fired", 0xd: "On, Return not detected", 0xf: "On, Return detected",
    0x10: "Off, Did not fire", 0x14: "Off, Did not fire, Return not detected", 0x18: "Auto, Did not fire",
    0x19: "Auto, Fired", 0x1d: "Auto, Fired, Return not detected", 0x1f: "Auto, Fired, Return detected",
    0x20: "No flash function", 0x30: "Off, No flash function", 0x41: "Fired, Red-eye reduction",
    0x45: "Fired, Red-eye reduction, Return not detected", 0x47: "Fired, Red-eye reduction, Return detected",
    0x49: "On, Red-eye reduction", 0x4d: "On, Red-eye reduction, Return not detected",
    0x4f: "On, Red-eye reduction, Return detected", 0x50: "Off, Red-eye reduction",
    0x58: "Auto, Did not fire, Red-eye reduction", 0x59: "Auto, Fired, Red-eye reduction",
    0x5d: "Auto, Fired, Red-eye reduction, Return not detected", 0x5f: "Auto, Fired, Red-eye reduction, Return detected"
    }
    _metadata_light_source_dictionary = {
    0: "Unknown", 1: "Daylight", 2: "Fluorescent", 3: "Tungsten (incandescent light)", 4: "Flash",
    9: "Fine weather", 10: "Cloudy weather", 11: "Shade", 12: "Daylight fluorescent (D 5700 - 7100K)",
    13: "Day white fluorescent (N 4600 - 5400K)", 14: "Cool white fluorescent (W 3900 - 4500K)",
    15: "White fluorescent (WW 3200 - 3700K)", 17: "Standard light A", 18: "Standard light B",
    19: "Standard light C", 20: "D55", 21: "D65", 22: "D75", 23: "D50", 24: "ISO studio tungsten"
    }
    _metadata_metering_list = [
    "Unknown", "Average", "Center-weighted average", "Spot", "Multi-spot", "Multi-segment", "Partial"
    ]
    _metadata_exposure_list = [
    "Not Defined", "Manual", "Program AE", "Aperture-priority AE", "Shutter speed priority AE",
    "Creative (Slow speed)", "Action (High speed)", "Portrait", "Landscape", "Bulb"
    ]
    _metadata_orientation_list = [
    "Horizontal (normal)", "Mirror horizontal", "Rotate 180", "Mirror vertical",
    "Mirror horizontal and rotate 270 CW", "Rotate 90 CW", "Mirror horizontal and rotate 90 CW", "Rotate 270 CW"
    ]
    _metadata_sensing_method_list = [
    "Not defined", "One-chip color area sensor", "Two-chip color area sensor", "Three-chip color area sensor",
    "Color sequential area sensor", "Trilinear sensor", "Color sequential linear sensor"
    ]
    _metadata_scene_capture_type_list = ["Standard", "Landscape", "Portrait", "Night scene"]
    _metadata_subject_distance_range_list = ["Unknown", "Macro", "Close view", "Distant view"]

    def _thumbnail(self, image, thumb_path, original_path, size, square=False):
        thumb_path = os.path.join(thumb_path, image_cache(self._path, size, square))
        info_string = f"{os.path.basename(original_path)} -> {size}px"
        if square:
            info_string += ", square"
        message("thumbing", info_string)
        if os.path.exists(thumb_path) and file_mtime(thumb_path) >= self._attributes["dateTimeFile"]:
            return
        gc.collect()
        try:
            image = image.copy()
        except KeyboardInterrupt:
            raise
        except Exception:
            try:
                image = image.copy()  # Retry to work around PIL bug
            except KeyboardInterrupt:
                raise
            except Exception:
                message("corrupt image", os.path.basename(original_path))
                return
        if square:
            if image.size[0] > image.size[1]:
                left = 0
                top = -(image.size[0] - image.size[1]) / 2
                right = image.size[0]
                bottom = image.size[1] + ((image.size[0] - image.size[1]) / 2)
            else:
                left = -(image.size[1] - image.size[0]) / 2
                top = 0
                right = image.size[0] + ((image.size[1] - image.size[0]) / 2)
                bottom = image.size[1]
            image = image.crop((left, top, right, bottom))
            gc.collect()
        image.thumbnail((size, size), Image.Resampling.LANCZOS)
        try:
            image.save(thumb_path, "JPEG", quality=88)
        except KeyboardInterrupt:
            try:
                os.unlink(thumb_path)
            except Exception:
                pass
            raise
        except Exception:
            message("save failure", os.path.basename(thumb_path))
            try:
                os.unlink(thumb_path)
            except Exception:
                pass

    def _thumbnails(self, image, thumb_path, original_path):
        mirror = image
        if self._orientation == 2:
            mirror = image.transpose(Image.FLIP_LEFT_RIGHT)
        elif self._orientation == 3:
            mirror = image.transpose(Image.ROTATE_180)
        elif self._orientation == 4:
            mirror = image.transpose(Image.FLIP_TOP_BOTTOM)
        elif self._orientation == 5:
            mirror = image.transpose(Image.FLIP_TOP_BOTTOM).transpose(Image.ROTATE_270)
        elif self._orientation == 6:
            mirror = image.transpose(Image.ROTATE_270)
        elif self._orientation == 7:
            mirror = image.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_270)
        elif self._orientation == 8:
            mirror = image.transpose(Image.ROTATE_90)
        for size in Photo.thumb_sizes:
            self._thumbnail(mirror, thumb_path, original_path, size[0], size[1])

    @property
    def name(self):
        return os.path.basename(self._path)

    def __str__(self):
        return self.name

    @property
    def path(self):
        return self._path

    @property
    def image_caches(self):
        return [image_cache(self._path, size[0], size[1]) for size in Photo.thumb_sizes]

    @property
    def date(self):
        if not self.is_valid:
            return datetime(1900, 1, 1)
        if "dateTimeOriginal" in self._attributes:
            return self._attributes["dateTimeOriginal"]
        elif "dateTime" in self._attributes:
            return self._attributes["dateTime"]
        return self._attributes["dateTimeFile"]

    def __lt__(self, other):
        return self.name < other.name

    @property
    def attributes(self):
        return self._attributes

    @staticmethod
    def from_dict(dictionary, basepath):
        del dictionary["date"]
        path = os.path.join(basepath, dictionary["name"])
        del dictionary["name"]
        for key, value in dictionary.items():
            if key.startswith("dateTime"):
                try:
                    dictionary[key] = datetime.strptime(dictionary[key], "%a %b %d %H:%M:%S %Y")
                except KeyboardInterrupt:
                    raise
                except Exception:
                    pass
        return Photo(path, None, dictionary)

    def to_dict(self):
        photo = {"name": self.name, "date": self.date}
        photo.update(self.attributes)
        return photo


class PhotoAlbumEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime("%a %b %d %H:%M:%S %Y")
        if isinstance(obj, Album) or isinstance(obj, Photo):
            return obj.to_dict()
        if isinstance(obj, TiffImagePlugin.IFDRational):
            if obj.denominator == 0:
                print("\033[91m Warning: 'nan' detected \033[0m")
                return float('nan')  # Return NaN to handle division by zero gracefully
            return float(obj)
        return super().default(obj)

