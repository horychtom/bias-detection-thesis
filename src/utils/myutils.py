import torch
import gc
import matplotlib.pyplot as plt
import itertools
import numpy as np
from torch.utils.data import DataLoader


from transformers import AutoModelForSequenceClassification,Trainer
from datasets import load_metric, Dataset, concatenate_datasets

def ratio(data):
    values = np.unique(data['label'],return_counts=True)[1]
    return [values[0]/np.sum(values),values[1]/np.sum(values)]

def compute_metrics_eval(eval_preds):
    metric = load_metric("f1")
    logits, labels = eval_preds
    predictions = np.argmax(logits, axis=-1)
    return metric.compute(predictions=predictions, references=labels)

def resample(data):
    data_biased = data.filter(lambda x: x['label'] == 1).shuffle(seed=42)
    data_unbiased = data.filter(lambda x: x['label'] == 0).shuffle(seed=42)

    if len(data_biased) < len(data_unbiased):
        data_unbiased = Dataset.from_dict(data_unbiased[:len(data_biased)])
    else: 
        data_biased = Dataset.from_dict(data_biased[:len(data_unbiased)])

    return concatenate_datasets([data_biased,data_unbiased]).shuffle(seed=42)

def preprocess_data(data,tokenizer,col_name:str):
    """tokenization and necessary processing

    Args:
        data (_type_): _description_
        tokenizer (_type_): _description_
        col_name (str): _description_

    Returns:
        _type_: _description_
    """
    tokenize = lambda data : tokenizer(data[col_name], truncation=True,max_length=128)
    
    data = data.map(tokenize,batched=True)
    data = data.remove_columns([col_name])
    data.set_format("torch")
    return data


def clean_memory():
    """cuda memory gets full while training transformers"""
    gc.collect()
    torch.cuda.empty_cache()


def compute_metrics(model,device,testing_dataloader):
    """computes F1 score and accuracy over dataset

    Args:
        model (any type): model for evaluation
        device : gpu or cpu on which are tensors mapped
        testing_dataloader (huggingface dataset): self explained

    Returns:
        dict: {"f1":score}
    """
    metric1 = load_metric("f1")
    metric2 = load_metric("accuracy")


    model.eval()
    for batch in testing_dataloader:
        batch = {k: v.to(device) for k, v in batch.items()}
        with torch.no_grad():
            outputs = model(**batch)

        logits = outputs.logits
        predictions = torch.argmax(logits, dim=-1)  
        metric1.add_batch(predictions=predictions, references=batch["labels"])
        metric2.add_batch(predictions=predictions, references=batch["labels"])
        
    return {'f1': metric1.compute(average='macro')['f1'],'accuracy': metric2.compute()}


def plot_confusion_matrix(cm, classes, normalize=False, title='Confusion matrix', cmap=plt.cm.Blues):
    """ convenient for plotting cm

    Args:
        cm (_type_): confusion matrix
        classes : labels for classes
        normalize (bool, optional):normalize to 1? Defaults to False.
        title : Defaults to 'Confusion matrix'.
        cmap (_type_, optional): Style .Defaults to plt.cm.Blues.
    """
    if normalize:
        cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
        print("Normalized confusion matrix")
    else:
        print('Confusion matrix, without normalization')

    print(cm)
    plt.imshow(cm, interpolation='nearest', cmap=cmap)
    plt.title(title)
    plt.colorbar()
    tick_marks = np.arange(len(classes))
    plt.xticks(tick_marks, classes, rotation=45)
    plt.yticks(tick_marks, classes)

    fmt = '.2f' if normalize else 'd'
    thresh = cm.max() / 2.
    for i, j in itertools.product(range(cm.shape[0]), range(cm.shape[1])):
        plt.text(j, i, format(cm[i, j], fmt), horizontalalignment="center", color="white" if cm[i, j] > thresh else "black")

    plt.tight_layout()
    plt.ylabel('True label')
    plt.xlabel('Predicted label')


def plot_losses(losses):
    loss_train = losses['Training Loss']
    loss_val = losses['Validation Loss']
    epochs = np.linspace(0.0, 5.0, num=len(loss_train))
    plt.plot(epochs, loss_train, 'g', label='Training loss')
    plt.plot(epochs, loss_val, 'b', label='validation loss')
    plt.title('Training and Validation loss')
    plt.xlabel('Epochs')
    plt.ylabel('Loss')
    plt.legend()
    plt.show()