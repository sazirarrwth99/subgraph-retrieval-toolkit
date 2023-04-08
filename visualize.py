"""Visualize the graph (represented as a set of triplets) using pyvis.
The visualized subgraphs are html files.
"""
import os
import argparse
import json
from pathlib import Path

import srsly
from pyvis.network import Network
from tqdm import tqdm
from bs4 import BeautifulSoup as Soup

from knowledge_graph import Wikidata


def visualize_subgraph(sample, wikidata):
    """Visualize the subgraph. It returns an html string.
    """
    net = Network(directed=True, font_color='#000000')
    net.barnes_hut()
    question_entities = sample['question_entities'] if 'question_entities' in sample else []
    answer_entities = sample['answer_entities'] if 'answer_entities' in sample else []
    # Add question entities even if they are not in the triplets
    for entity in question_entities:
        net.add_node(entity, label=wikidata.get_label(entity), color='#114B7A')
    for triplet in sample['triplets']:
        subject, relation, obj = triplet
        subject_label = wikidata.get_label(subject)
        subject_options = {'color':'#114B7A'} if subject in question_entities else {}
        obj_label = wikidata.get_label(obj)
        obj_options = {'color':'#1B5E20'} if obj in answer_entities else {}
        relation_label = wikidata.get_label(relation)
        net.add_node(subject, label=subject_label, **subject_options)
        net.add_node(obj, label=obj_label, **obj_options)
        net.add_edge(subject, obj, label=relation_label)

    net_options = {
        'shape': 'dot',
        'font': {
            'size': '1em',
            'face': 'fontFace',
            'strokeColor': '#fff',
            'strokeWidth': 5
        },
        'size': '1.5em',
    }
    net.set_options(json.dumps(net_options))
    return net.generate_html(notebook=False)


def add_text_to_html(html, text):
    soup = Soup(html, 'html.parser')
    style_tag = soup.new_tag('style')
    style_tag.string = '''
        .background-text {
            position: absolute;
            z-index: 1;
            top: 0;
            left: 0;
            font-size: 2em;
            color: #ccc;
        }
    '''
    soup.head.append(style_tag)
    p_tag = soup.new_tag('p', attrs={'class': 'background-text'}, style="white-space:pre-wrap")
    p_tag.string = text
    soup.body.append(p_tag)
    return soup.prettify()
    

def main(args):
    wikidata = Wikidata(args.wikidata_endpoint)
    samples = srsly.read_jsonl(args.input)
    total = sum(1 for _ in srsly.read_jsonl(args.input))
    total = min(total, args.max_output)
    if not os.path.exists(args.output_dir):
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        print(f'Created output directory: {args.output_dir}')
    for i, sample in enumerate(tqdm(samples, desc='Visualizing graphs', total=total)):
        if i >= args.max_output:
            break
        html = visualize_subgraph(sample, wikidata)
        text_to_append = f"Question: {sample['question']}"
        if 'answer' in sample:
            text_to_append += f"\n    Answer: {sample['answer']}"
        html = add_text_to_html(html, text_to_append)
        output_path = os.path.join(args.output_dir, sample['id'] + '.html')
        with open(output_path, 'w', encoding='utf-8') as fout:
            fout.write(html)
    print(f'Visualized graphs outputted to {args.output_dir}.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--wikidata-endpoint', type=str, default='http://localhost:1234/api/endpoint/sparql',
                        help='endpoint of the wikidata sparql service')
    parser.add_argument('--input', help='The input subgraph file path.')
    parser.add_argument('--output-dir', help='The output directory path.')
    parser.add_argument('--max-output', type=int, default=1000, help='The maximum number of graphs to output.')
    args = parser.parse_args()
    main(args)
