# Making imports convenient
import sys
import os

PATH = '/home/horyctom/bias-detection-thesis'
sys.path.insert(1, PATH)


import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader
from datasets import load_dataset, Dataset,concatenate_datasets
import transformers
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import StratifiedKFold

from transformers import AutoTokenizer, DataCollatorWithPadding,AutoModelForSequenceClassification,AdamW,get_scheduler,TrainingArguments,Trainer,EarlyStoppingCallback
from sklearn.model_selection import ParameterGrid
from src.utils.myutils import *
import json

device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")

CS_DATA_PATH = PATH + '/data/CS/processed/BABE/train.csv'

#load data
data = load_dataset('csv',data_files = CS_DATA_PATH)['train']
skfold = StratifiedKFold(n_splits=10, shuffle=True, random_state=42)

#model 
model_name = 'fav-kky/FERNET-C5'
tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=False,padding=True)
data_collator = DataCollatorWithPadding(tokenizer=tokenizer)
token_full = preprocess_data(data,tokenizer,'sentence')

def fit_and_eval(model_name,token_full,train_idx,eval_idx,training_args):
    token_train = Dataset.from_dict(token_full[train_idx])
    token_valid = Dataset.from_dict(token_full[eval_idx])
    
    model = AutoModelForSequenceClassification.from_pretrained(model_name,num_labels=2);
    model.to(device);
    trainer = Trainer(model,training_args,train_dataset=token_train,data_collator=data_collator,tokenizer=tokenizer)
    
    trainer.train();
    #evaluation
    eval_dataloader = DataLoader(token_valid, batch_size=BATCH_SIZE, collate_fn=data_collator);
    return compute_metrics(model,device,eval_dataloader)['f1']


param_grid = {
     'learning_rate':[2e-5,3e-5,4e-5],
     'batch_size': [32],
     'number_of_epochs':[2,3,4]}

param_comb = ParameterGrid(param_grid)

with open(PATH + '/src/models/fernet_hyperparam_search.txt','w') as f:
    for idx,params in enumerate(param_comb):

        BATCH_SIZE = params['batch_size']
        training_args = TrainingArguments(
            output_dir = './',
            num_train_epochs=params['number_of_epochs'],
            save_total_limit=2,
            disable_tqdm=False,
            per_device_train_batch_size=params['batch_size'],  
            warmup_steps=0,
            weight_decay=0.1,
            learning_rate=params['learning_rate'])

        scores = []

        #run 5-fold CV
        for train_index, val_index in skfold.split(token_full['input_ids'],token_full['label']):
            scores.append(fit_and_eval(model_name,token_full,train_index,val_index,training_args));

        f.write(json.dumps(params))
        f.write(" f1: " + str(np.mean(scores))+"\n")
