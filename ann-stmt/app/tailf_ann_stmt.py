#!/usr/bin/env python3
import argparse
import os
import subprocess
from bs4 import BeautifulSoup
import re
from datetime import datetime
import copy


def gen_ann_module(name, ns, prefix):
    revdate = datetime.today().strftime('%Y-%m-%d')
    str = """<?xml version="1.0" encoding="utf-8"?>
<module>
  <namespace uri="{}-ann"/>
  <prefix value="{}-ann"/>
  <import module="tailf-common">
    <prefix value="tailf"/>
  </import>
  <revision date="{}">
    <description>
      <text>Initial revision</text>
    </description>
  </revision>
  <tailf_prefix_annotate_module module_name="{}"/>
</module>""".format(ns,prefix,revdate,name)
    return str


def add_stmt(node, ann_node, ann_soup):
    if node.parent.name == "module" or node.parent.name == "submodule":
        return ann_node
    elif node.parent.name == "augment":
        parent_ann_node = ann_soup.new_tag("tailf:annotate-statement", statement_path="{}[name=\'{}\']".format(node.parent.name, node.parent['target_node']))
    else:
        parent_ann_node = ann_soup.new_tag("tailf:annotate-statement", statement_path="{}[name=\'{}\']".format(node.parent.name, node.parent['yname']))
    parent_ann_node.append(ann_node)
    return add_stmt(node.parent, parent_ann_node, ann_soup)


def tailf_ann_stmt(yang_file):
    confd_dir = os.environ['CONFD_DIR']
    yang_file_path = yang_file.rsplit('/', 1)
    yang_path = yang_file_path[0]
    yang_filename = yang_file_path[1]
    ann_filename = "{}-ann.yang".format(yang_filename.rsplit('.', 1)[0])
    result = subprocess.run(['python3', '/usr/local/bin/pyang', '-f', 'yin',
                            '-p', yang_path, '-p', confd_dir, yang_file],
                            stdout=subprocess.PIPE, encoding='utf-8')
    yin_content = result.stdout
    yin_content = yin_content.replace('tailf:', 'tailf_prefix_')
    yin_content = yin_content.replace('name=', 'yname=')
    yin_content = yin_content.replace('target-node=', 'target_node=')
    yin_content = yin_content.replace('xmlns:', 'xmlns_')
    yin_soup = BeautifulSoup(yin_content, "xml")
    if yin_soup.module is not None:
        annotate_module = gen_ann_module(yang_filename.rsplit('.', 1)[0],
                                         yin_soup.module.find('namespace')['uri'],
                                         yin_soup.module.find('prefix')['value'])
    elif yin_soup.submodule is not None:
        prefix = yin_soup.submodule.find('prefix')['value']
        annotate_module = gen_ann_module(yang_filename.rsplit('.', 1)[0],
                                         yin_soup.submodule["xmlns_{}".format(prefix)],
                                         prefix)
    else:
        print("Error: Unknown module type. Neither a YANG module or submodule ")
        return
    ann_soup = BeautifulSoup(annotate_module, "xml")
    for tailf_extension in yin_soup.find_all(re.compile('tailf_prefix_')):
        if tailf_extension.parent is not None and tailf_extension.parent.name.startswith('tailf_prefix_') == False:
            annotate_statements = add_stmt(tailf_extension, copy.copy(tailf_extension), ann_soup)
            ann_soup.module.tailf_prefix_annotate_module.append(annotate_statements)
            tailf_extension.decompose()
    tailf_import = yin_soup.find('import', module='tailf-common')
    if tailf_import is None:
        create_ann_module = False
    else:
        create_ann_module = True
        tailf_import.decompose()
    tailf_ann_import = ann_soup.find('import', module='tailf-common')
    if yin_soup.module is not None:
        ann_soup.module.attrs = copy.copy(yin_soup.module.attrs)
        for module_import in yin_soup.module.find_all('import', recursive=False):
            tailf_ann_import.insert_before(copy.copy(module_import))
    else:
        ann_soup.module.attrs = copy.copy(yin_soup.submodule.attrs)
        for module_import in yin_soup.submodule.find_all('import', recursive=False):
            tailf_ann_import.insert_before(copy.copy(module_import))
    ann_soup.module['yname'] = "{}-ann".format(ann_soup.module['yname'])
    yin_soup_str = str(yin_soup)
    yin_soup_str = yin_soup_str.replace('tailf_prefix_', 'tailf:')
    yin_soup_str = yin_soup_str.replace('yname=', 'name=')
    yin_soup_str = yin_soup_str.replace('target_node=', 'target-node=')
    yin_soup_str = yin_soup_str.replace('xmlns_', 'xmlns:')
    result = subprocess.run(['python3', '/usr/local/bin/pyang', '-f',
                            'yang', '-p', yang_path, '-p', confd_dir],
                            stdout=subprocess.PIPE, input=yin_soup_str,
                            encoding='utf-8')
    yang_content = result.stdout
    with open("yang/{}".format(yang_filename), "w") as fp:
        fp.write(str(yang_content))
        fp.close()
    if create_ann_module is True:
        ann_soup_str = str(ann_soup)
        ann_soup_str = ann_soup_str.replace('tailf_prefix_', 'tailf:')
        ann_soup_str = ann_soup_str.replace('annotate_module', 'annotate-module')
        ann_soup_str = ann_soup_str.replace('module_name=', 'module-name=')
        ann_soup_str = ann_soup_str.replace('statement_path=', 'statement-path=')
        ann_soup_str = ann_soup_str.replace('yname=', 'name=')
        ann_soup_str = ann_soup_str.replace('target_node=', 'target-node=')
        ann_soup_str = ann_soup_str.replace('xmlns_', 'xmlns:')
        result = subprocess.run(['python3', '/usr/local/bin/pyang', '-f',
                                'yang', '--ignore-error=UNUSED_IMPORT', '-p',
                                yang_path, '-p', confd_dir], stdout=subprocess.PIPE,
                                input=ann_soup_str, encoding='utf-8')
        ann_content = result.stdout
        with open("yang/{}".format(ann_filename), "w") as fp:
            fp.write(str(ann_content))
            fp.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('filename', nargs=1, type=str,
                        help='<file> YANG module to be sanitized')
    args = parser.parse_args()
    tailf_ann_stmt(args.filename[0])
