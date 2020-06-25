import sys

if sys.version_info[0] < 3:
    sys.stderr.write("You need Python 3 or later to run this script!\n")
    sys.exit(1)


def add_subparser(module_name, subparsers):
    parser = subparsers.add_parser(module_name, help='Задачи разбиения видео на фрагменты')
    parser.set_defaults(command=module_name)


def main(parsed_args=None):
    if parsed_args is None:
        return


if __name__ == "__main__":
    pass
