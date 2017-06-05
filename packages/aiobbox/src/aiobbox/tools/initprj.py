import os, sys
import uuid
import json
import argparse

parser = argparse.ArgumentParser(
    description='init a bbox project')
parser.add_argument(
    '--language',
    type=str,
    default='python3',
    help='the language, default is python3')
parser.add_argument(
    '--prefix',
    type=str,
    default='',
    help='cluster prefix, a cluster of boxes share the prefix')

def main():
    args = parser.parse_args()


    config_file = os.path.join(os.getcwd(), 'bbox.config.json')
    
    if os.path.exists(config_file):
        print('project already initialized!',
              file=sys.stderr)
        sys.exit(1)

    prjname = os.path.basename(os.getcwd())
    
    lang = args.language
    if lang not in ('python3', 'python'):
        print('language {} not supported'.format(lang),
              file=sys.stderr)
        sys.exit(1)

    if lang == 'python':
        lang = 'python3'

    config_json = {
        'name': prjname,
        'etcd': ['127.0.0.1:2379'],
        'prefix': args.prefix or uuid.uuid4().hex,
        'language': lang,
        'port_range': [30000, 31000],
        'bind_ip': '127.0.0.1'
        }
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config_json, f, indent=2, sort_keys=True)

if __name__ == '__main__':
    main()
