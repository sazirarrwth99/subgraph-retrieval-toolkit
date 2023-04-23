"""The script to train the scorer model.

e.g.
python train.py --data-file data/train.jsonl --model-name-or-path intfloat/e5-small --save-model-path artifacts/scorer
"""
import argparse
import datetime
from collections import defaultdict
from dataclasses import dataclass

import lightning.pytorch as pl
import torch
from datasets import load_dataset
from lightning.pytorch.loggers import WandbLogger
from torch.utils.data import DataLoader
from transformers import AutoTokenizer, PreTrainedTokenizerBase

from .scorer import LitSentenceEncoder


def concate_all(example):
    """Concatenate all columns into one column for input.
    The resulted 'input_text' column is a list of strings.
    """
    query = 'query: ' + example['query']
    rels = [example['positive']] + example['negatives']
    rels = ['relation: ' + rel for rel in rels]
    example['input_text'] = [query] + rels
    return example


@dataclass
class Collator:
    """Collate a list of examples into a batch."""
    tokenizer: PreTrainedTokenizerBase

    def __call__(self, features):
        batched = defaultdict(list)
        for item in features:
            for key, value in item.items():
                value = torch.tensor(value)
                if key == 'attention_mask':
                    value = value.bool()
                batched[key].append(value)
        for key, value in batched.items():
            batched[key] = torch.stack(value, dim=0)
        return batched


def prepare_dataloaders(data_file, tokenizer, batch_size):
    """Prepare dataloaders for training and validation."""
    def tokenize(example):
        tokenized = tokenizer(example['input_text'], padding='max_length', truncation=True, return_tensors='pt', max_length=32)
        return tokenized
    train_dataset = load_dataset('json', data_files=data_file, split='train[:95%]')
    train_dataset = train_dataset.map(concate_all, remove_columns=train_dataset.column_names)
    train_dataset = train_dataset.map(tokenize, remove_columns=train_dataset.column_names)
    validation_dataset = load_dataset('json', data_files=data_file, split='train[95%:]')
    validation_dataset = validation_dataset.map(concate_all, remove_columns=validation_dataset.column_names)
    validation_dataset = validation_dataset.map(tokenize, remove_columns=validation_dataset.column_names)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, collate_fn=Collator(tokenizer), num_workers=8)
    validation_loader = DataLoader(validation_dataset, batch_size=batch_size, shuffle=False, collate_fn=Collator(tokenizer), num_workers=8)
    return train_loader, validation_loader


def main(args):
    model = LitSentenceEncoder(args.model_name_or_path)
    tokenizer = AutoTokenizer.from_pretrained(args.model_name_or_path)
    train_loader, validation_loader = prepare_dataloaders(args.input, tokenizer, args.batch_size)
    day_hour = datetime.datetime.now().strftime('%d-%H')
    wandb_logger = WandbLogger(project='retrieval', name=day_hour , group='contrastive', save_dir='artifacts')
    trainer = pl.Trainer(accelerator=args.accelerator, default_root_dir=args.output_dir,
                         fast_dev_run=args.fast_dev_run, max_epochs=args.max_epochs, logger=wandb_logger)
    trainer.fit(model, train_dataloaders=train_loader, val_dataloaders=validation_loader)
    model.save_huggingface_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)


def add_arguments(parser):
    """Add train arguments to a parser in place."""
    parser.add_argument('-i', '--input', default='data/retrieval/train.jsonl',
                        help='training data for the scorer. It should be a JSONL file with fields: query, positive, negatives')
    parser.add_argument('-o', '--output-dir', default='artifacts/scorer',
                        help='output model path. the model will be saved in the format of huggingface models,\
                        which can be uploaded to the huggingface hub and shared with the community.')
    parser.add_argument('--model-name-or-path', default='intfloat/e5-small',
                        help='pretrained model name or path. It is fully compatible with HuggingFace models.\
                        You can specify either a local path where a model is saved, or an encoder model identifier\
                        from huggingface hub, e.g. bert-base-uncased.')
    parser.add_argument('--batch-size', default=16, type=int, help='batch size')
    parser.add_argument('--max-epochs', default=10, type=int, help='max epochs')
    parser.add_argument('--accelerator', default='gpu', help='accelerator, can be cpu, gpu, or tpu')
    parser.add_argument('--fast-dev-run', action='store_true',
                        help='fast dev run for debugging, only use 1 batch for training and validation')

if __name__ == '__main__':
    torch.set_float32_matmul_precision('medium')
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    args = parser.parse_args()

    main(args)
