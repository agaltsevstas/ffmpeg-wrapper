import os
import sys
import argparse
import pkgutil
import inspect

if sys.version_info[0] < 3:
    sys.stderr.write("You need Python 3 or later to run this script!\n")
    sys.exit(1)

DEFAULT_MODULES_DIRNAME = "modules"


# modules_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'modules')
def get_modules(subparsers):
    modules = {}
    modules_root = os.path.dirname(os.path.realpath(__file__))
    for sub_dir in (x for x in os.listdir(modules_root) if os.path.isdir(os.path.join(modules_root, x))):

        if not sub_dir.startswith(('.', '__')):

            for module_finder, name, ispkg in pkgutil.iter_modules(path=[os.path.join(modules_root, sub_dir), ]):

                module = module_finder.find_module(name).load_module(name)

                if sub_dir != DEFAULT_MODULES_DIRNAME:
                    name = '{}/{}'.format(sub_dir, name)
                modules[name] = module

                for function_name, function in inspect.getmembers(module, inspect.isfunction):
                    if function_name == 'add_subparser':
                        function(name, subparsers)
    return modules


def main():
    parser = argparse.ArgumentParser(description='Modular FFMPEG Wrapper')
    subparsers = parser.add_subparsers(help='Available modules')
    subparsers.required = True

    parser.add_argument('-i', '--input', type=os.path.abspath, nargs='+', metavar='file/directory',
                        required=True, action='store', help='Input data (files or folders separated by a space)')
    parser.add_argument('-o', '--output_directory', type=os.path.abspath, metavar='dirname',
                        action='store', help='Root directory for processed data')
    parser.add_argument('-r', '--recursive', action='store_true', help='Recursive processing of input directories')
    parser.add_argument('--debug', action='store_true', help='Debug mode')

    modules = get_modules(subparsers)

    args = parser.parse_args(['--help', ] if len(sys.argv) == 1 else None)

    if args.debug:
        print(args)
        print(modules)
        sys.exit(0)

    try:
        modules[args.command].main(vars(args))
    except (AttributeError, KeyError):
        print('Call module "{}" error.'.format(args.command))
        sys.exit(1)


if __name__ == "__main__":
    main()
