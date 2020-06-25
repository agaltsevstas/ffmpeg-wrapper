import sys

if sys.version_info[0] < 3:
    sys.stderr.write("You need Python 3 or later to run this script!\n")
    sys.exit(1)

import argparse
import re
from pathlib import Path
from natsort import natsorted

time_pattern = re.compile(r"([01]?[0-9]|2[0-3])_([0-5][0-9])_([0-5][0-9])")
sub_pattern = re.compile(r"(\s?\(\w+\))")

IMAGE_FORMAT = ('.png', '.jpg')


def abspath(path_string):
    return Path(path_string).absolute()


def sorted_glob(pathlike_dir):
    for ext in IMAGE_FORMAT:
        yield from natsorted(pathlike_dir.glob('**/*' + ext))


def parse_ars():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=abspath, action='store', help="")
    return vars(parser.parse_args())


def get_name(image):
    dirname = image.parent.name
    pref = image.parent.parent.name.replace('_', '')

    if pref.startswith('20'):
        pref = pref[2:]

    unbracket = re.sub(sub_pattern, '', pref)
    if unbracket is not None:
        unbracket = unbracket.strip()
        if len(unbracket) == 6:
            pref = unbracket

    try:
        hour = re.match(time_pattern, dirname).group(1)
    except AttributeError as err:
        pass
    else:

        dirname = image.parent.name.replace('_', '')

        output_dir = image.parent.parent / "{}_{}".format(pref, hour)
        output_dir.mkdir(parents=True, exist_ok=True)
        ext = image.suffix

        try:
            frame_number = int(image.stem.rsplit('_', maxsplit=1)[-1])
        except ValueError as err:
            filename = "{}_{}_{}".format(pref, dirname, image.name)
        else:
            filename = "{}_{}_{:0=6}{}".format(pref, dirname, frame_number, ext)

        return output_dir / filename


def main():
    args = parse_ars()

    directory = args['directory']

    if not directory.is_dir():
        raise NotADirectoryError(str(directory.resolve()))

    sub_dirs = set()

    for image in sorted_glob(directory):
        sub_dirs.add(image.parent)
        name = get_name(image)
        if name is not None:
            if name.exists():
                print(name + " : Exists!")
            else:
                image.replace(name)
        else:
            print("{} - skipped!".format(image))

    for sd in sub_dirs:
        try:
            sd.rmdir()
        except OSError as err:
            print(err)


if __name__ == "__main__":
    main()
