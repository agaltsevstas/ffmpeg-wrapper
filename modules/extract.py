import sys
import itertools
import re
import uuid
import subprocess as sp
from pathlib import Path
from functools import partial

if sys.version_info[0] < 3:
    sys.stderr.write("You need Python 3 or later to run this script!\n")
    sys.exit(1)

MEDIA_FORMAT = (".avi", ".mp4")
IMAGE_FORMAT = ("png", "jpg", "bmp")


def add_subparser(module_name, subparsers):
    parser = subparsers.add_parser(module_name, help='Задачи извлечения кадров из видео')
    parser.set_defaults(command=module_name)
    parser.add_argument("--format", type=str, default="png", choices=IMAGE_FORMAT,
                        help="Формат извлекаемых кадров.", action="store")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-f", "--frame_interval", type=int, action="store",
                       help="Значение шага извлечения (в кадрах)")
    group.add_argument('-t', '--time_interval', type=lambda x: int(float(x) * 1000), action='store',
                       help='Значение интервала времени извлечения кадров (в секундах) ')
    group.add_argument('-a', '--extract_all', help='Извлечь все кадры', action='store_true')


def walk_on_tree(path_list, root_output_dir, recursive=False):
    """Принимает список path-like объектов, и возможную директорию для выходных файлов.
    Флаг recursive устанавливает режим обхода директорий в path_list (если присутствуют).
    На каждой итерации yield возвращает кортеж из двух элементов: медиафайла и выходной директории для этого медиафайла
     в зависимости от аргумента ком.строки 'output'.
    """
    glob_pattern = '**/*' if recursive else '*'
    for path in path_list:
        if path.exists():
            if path.is_file() and path.suffix.lower().endswith(MEDIA_FORMAT):
                output_dir = path.parent if root_output_dir is None else root_output_dir
                yield path, output_dir
            elif path.is_dir():
                output_dir = path if root_output_dir is None else root_output_dir
                yield from ((media, output_dir.joinpath(media.parent.relative_to(path)))
                            for media in itertools.chain.from_iterable(path.glob(glob_pattern + ext)
                            for ext in MEDIA_FORMAT))
        else:
            print('{} - not exists! Skip.'.format(str(path)))


sort_pattern = re.compile(r"(\d+)")


def native_sort(path):
    result = []
    for part in path.parts:
        for x in re.split(sort_pattern, part):
            if not x:
                continue
            if x.isdigit() and len(x) < 16:
                x = "{:0=16}".format(int(x))
            result.append(x)
    return result


def sorted_glob_with_prefix(pathlike_dir, prefix=''):
    for ext in IMAGE_FORMAT:
        yield from sorted(pathlike_dir.glob('{}*.{}'.format(prefix, ext)), key=native_sort)


class ExtractionTask:

    def __init__(self, media, root_dir, frame_format='png'):
        if not isinstance(media, Path) and isinstance(media, str):
            media = Path(media)
        if not (media.exists() and media.is_file()):
            raise FileNotFoundError(str(media))
        if not isinstance(root_dir, Path) and isinstance(root_dir, str):
            root_dir = Path(root_dir)

        self.__id = uuid.uuid4()
        self.__media = media
        self.__output_dir = root_dir / self.__media.stem
        self.__output_dir.mkdir(parents=True, exist_ok=True)
        self.__ext = frame_format
        self.__fps = self.get_fps(self.media)

        self.__actions = []
        self.__post_actions = []

    @property
    def fps(self):
        return self.__fps

    @property
    def id(self):
        return self.__id

    @property
    def media(self):
        return self.__media

    @property
    def output_dir(self):
        return self.__output_dir

    @property
    def ext(self):
        return self.__ext

    @property
    def actions(self):
        return tuple(self.__actions)

    def add_actions(self, *args):
        if not all(map(callable, args)):
            raise TypeError('Some item in args not callable')
        self.__actions.extend(args)

    @property
    def post_actions(self):
        return tuple(self.__post_actions)

    def add_post_actions(self, *args):
        if not all(map(callable, args)):
            raise TypeError('Some item in args not callable')
        self.__post_actions.extend(args)

    def __len__(self):
        return len(self.actions + self.post_actions)

    def __iter__(self):
        return iter(self.actions + self.post_actions)

    def __str__(self):
        return '\n'.join(
            ('ExtractionTask:', 'ID: '+str(self.id), 'MEDIA: '+str(self.media), 'OUTPUT_DIR: '+str(self.output_dir),
             'IMAGE_FORMAT: '+self.ext,
             ('\n'+' '*4).join(map(str, ['Actions:'] + list(self.actions))),
             ('\n'+' '*4).join(map(str, ['Postprocess:'] + list(self.post_actions)))
             )
        )

    @staticmethod
    def get_fps(media):
        if not isinstance(media, Path) and isinstance(media, str):
            media = Path(media)
        if not (media.exists() and media.is_file()):
            raise FileNotFoundError(str(media))
        if media.suffix.lower() not in MEDIA_FORMAT:
            print('Unsupported MEDIA_FORMAT: {}'.format(media.suffix))
            return None
        try:
            ffprobe_output = sp.check_output(
                [
                 'ffprobe', '-v', '0', '-of', 'csv=p=0', '-select_streams', 'v:0',
                 '-show_entries', 'stream=r_frame_rate', str(media),
                ]
            )

            fps = float(eval(ffprobe_output.decode('utf8').strip('\n')))
        except (sp.CalledProcessError, UnicodeDecodeError, AttributeError) as e:
            print(e)
        except (SyntaxError, ValueError) as err:
            print(err)
        else:
            return fps
        return None


def cut_microseconds_in_dirname(directory):
    try:
        date, time, camera_code = directory.name.split('_')
        seconds, milliseconds = time.split('.')
    except (ValueError, AttributeError) as err:
        print(err)
        print('{} - was not renamed'.format(str(directory)))
    else:
        directory.rename(
            directory.parent / '_'.join((date, '{}.{}'.format(seconds, milliseconds[:-3]), camera_code)))


def correct_filenames(directory, uid, interval=1, is_time_interval=False):
    if not isinstance(directory, Path):
        raise TypeError('Positional argument "directory" has unexpected type: {}'.format(type(directory)))
    elif not (directory.exists() and directory.is_dir()):
        raise NotADirectoryError(str(directory))
    if not isinstance(uid, uuid.UUID):
        raise TypeError('Positional argument "uid" has unexpected type: {}'.format(type(uid)))
    if not isinstance(interval, int):
        raise TypeError('Keyword argument "interval" has unexpected type: {}'.format(type(interval)))
    elif interval <= 0:
        raise ValueError('Interval <= 0')

    for img in sorted_glob_with_prefix(directory, str(uid) + '_'):
        try:
            prefix, index = img.stem.rsplit('_', maxsplit=1)
            assert str(uid) == prefix, 'Prefix not equal for frame: {}'.format(str(img))
            assert index.isdigit() is True, 'Frame_number not digit for frame: {}'.format(str(img))
            index = int(index) - 1
        except (ValueError, AttributeError):
            print('Skip: ' + str(img))
        except AssertionError:
            print('AssertionError. Skip: ' + str(img))
        else:
            img.rename(img.parent / '{}{}'.format(index * interval + (1 if not is_time_interval else 0), img.suffix))


# REGISTRATE OPERATIONS TO ACTION_MAP
ACTION_MAP = {}


# closure
def register_operation(operation_name):
    def wrapper(func):
        if operation_name in ACTION_MAP:
            raise ValueError('Action "{}" already exists in ACTION_MAP'.format(operation_name))
        ACTION_MAP[operation_name] = func
        return func
    return wrapper


@register_operation('frame_interval')
def extract_by_frame_interval(task, frame_interval=1):
    if not isinstance(frame_interval, int):
        raise TypeError('Frame interval must be INT')
    if not frame_interval >= 1:
        raise ValueError('Frame interval must be >= 1')

    if task.fps is None:
        print("Can't get FPS from: {}".format(str(task.media)))
        return

    cmd = [
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(task.media), '-threads', '0', '-crf', '0', '-preset', 'veryslow',
        '-vf', "select=not(mod(n\\,{}))".format(frame_interval), '-vsync', 'vfr',
        str(task.output_dir / "{}_%d.{}".format(str(task.id), task.ext)),
    ]

    task.add_actions(
        partial(sp.run, cmd),
    )
    task.add_post_actions(
        partial(correct_filenames, task.output_dir, task.id, interval=frame_interval, is_time_interval=False),
    )


@register_operation('time_interval')
def extract_by_time_interval(task, time_interval=1):
    if not isinstance(time_interval, int):
        raise TypeError('Time interval must be INT')
    if not time_interval >= 1:
        raise ValueError('Time interval must be gt 0')

    if task.fps is None:
        print("Can't get FPS from: {}".format(str(task.media)))
        return

    cmd = [
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(task.media), '-threads', '0', '-crf', '0', '-preset', 'veryslow',
        '-vf', "select=between(mod(n\\, {0})\\, 0\\, 0), setpts=N/{1}/TB".format(task.fps*time_interval/1000, task.fps),
        str(task.output_dir / '{}_%d.{}'.format(str(task.id), task.ext)),
    ]

    task.add_actions(
        partial(sp.run, cmd),
    )
    task.add_post_actions(
        partial(correct_filenames, task.output_dir, task.id, interval=time_interval, is_time_interval=True),
    )


@register_operation('extract_all')
def extract_all(task, *args):
    extract_by_frame_interval(task)

    
def main(parsed_args=None):
    if parsed_args is None:
        return

    arg_list = [attr for attr in (ACTION_MAP.keys() & parsed_args.keys()) if parsed_args[attr]]

    if len(arg_list) != 1:
        print((ACTION_MAP.keys() & parsed_args.keys()))
        print(arg_list)
        raise ValueError('Not single action in arguments.')

    arg = arg_list.pop()
    value = parsed_args[arg]

    handler = ACTION_MAP[arg]

    tasks = [
        ExtractionTask(media, output_dir, frame_format=parsed_args['format'])
        for media, output_dir in walk_on_tree(map(Path, parsed_args['input']),
                                              Path(parsed_args['output_directory']),
                                              parsed_args['recursive'],
                                              )
    ]

    for task in tasks:
        handler(task, value)
        for action in task:
            action()

    # Fix broken terminal after ffmpeg completed work
    # https://bugs.launchpad.net/ubuntu/+source/gnome-terminal/+bug/1756952
    # sp.run('reset')
    # print('All tasks done!')


if __name__ == "__main__":
    pass
