from functools import lru_cache

import torch
import torch.nn.functional as F
from transformers import AutoTokenizer

from .encoder import LitSentenceEncoder


class Scorer:
    """Scorer for relation paths."""

    def __init__(self, pretrained_name_or_path):
        self.model = LitSentenceEncoder(pretrained_name_or_path)
        config = self.model.config
        self.tokenizer = AutoTokenizer.from_pretrained(config._name_or_path)

    @lru_cache
    def score(self, question, prev_relations, next_relation):
        """Score a relation path.

        Args:
            question (str): question
            prev_relations (tuple[str]): tuple of relation **labels** that have been traversed.
            next_relation (str): next relation to be traversed
        """
        # Prepending 'query' and 'relation' corresponds to the way the model was trained (check collate_fn)
        query = f"query: {question} [SEP] {' # '.join(prev_relations)}"
        next_relation = 'relation: ' + next_relation
        text_pair = [query, next_relation]
        inputs = self.tokenizer(text_pair, return_tensors='pt', padding=True)
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = self.model(**inputs, return_dict=True)
            pooled_embeddings = self.model.average_pool(
                outputs.last_hidden_state, inputs['attention_mask'])
            distance = F.cosine_similarity(
                pooled_embeddings[0], pooled_embeddings[1], dim=-1)
        return distance.item()
