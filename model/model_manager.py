import os

import numpy as np
import torch
import torch.nn as nn
import wandb
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    plot_confusion_matrix,
    plot_roc_curve
)

from model import __version__
from model.config import config
from utlis import plot_confusion_matrix

wandb.init('Common-Voice', config=config.ALL_PARAM)


def _metric_summary(pred: np.ndarray, label: np.ndarray):
    acc = accuracy_score(y_true=label, y_pred=pred)
    f1 = f1_score(y_true=label, y_pred=pred)
    pc = precision_score(y_true=label, y_pred=pred)
    rs = recall_score(y_true=label, y_pred=pred)
    return acc, f1, pc, rs


class EarlyStopping:
    """
    Early stops the training if validation loss doesn't improve after a given threshold.
    """

    def __init__(
            self, threshold: int = 50, verbose: bool = False, delta: float = 0
    ) -> None:
        """
        :param threshold: How long to wait after last time validation loss improved. Default: 50
        :param verbose: If True, prints a message for each validation loss improvement.Default: False
        :param delta: Minimum change in the monitored quantity to qualify as an improvement.Default: 0
        """

        self.threshold = threshold
        self.verbose = verbose
        self.counter = 0
        self.best_score = None
        self.early_stop = False
        self.val_loss_min = np.Inf
        self.delta = delta

    def __call__(self, val_loss, model):

        score = -val_loss

        if self.best_score is None:
            self.best_score = score
            self.save_checkpoint(val_loss, model)

        elif score < self.best_score + self.delta:
            self.counter += 1
            print(f"EarlyStopping counter: {self.counter} out of {self.threshold}")

            if self.counter >= self.threshold:
                self.early_stop = True
        else:
            self.best_score = score
            self.save_checkpoint(val_loss, model)
            self.counter = 0

    def save_checkpoint(self, val_loss, model):
        """Saves RNN_TYPE when validation loss decrease."""
        if self.verbose:
            print(
                f"Validation loss decreased ({self.val_loss_min:.6f} --> {val_loss:.6f}).  Saving RNN_TYPE ..."
            )

        torch.save(
            model.state_dict(),
            "./trained_model/" + "/model_gender_{}.pt".format(__version__),
        )
        self.val_loss_min = val_loss


def train(
        model: object,
        train_loader: torch.utils.data.dataloader.DataLoader,
        valid_loader: torch.utils.data.dataloader.DataLoader,
        learning_rate: float = config.TRAIN_PARAM['LEARNING_RATE'],
        print_every: int = 10,
        epoch: int = config.TRAIN_PARAM['EPOCH'],
        gradient_clip: int = config.TRAIN_PARAM['GRADIENT_CLIP'],
        early_stopping_threshold: int = 50,
        early_stopping: bool = True,
) -> object:
    """
    :param model:  Torch model to
    :param train_loader:  Training Folder Datafolder
    :param valid_loader: Validation Folder Data Folder
    :param learning_rate: Learning rate to improve loss function
    :param print_every: Iteration to print model results and validation
    :param epoch: Number of times to pass though the entire data folder
    :param gradient_clip:
    :param early_stopping_threshold:  threshold to stop running model
    :param early_stopping: Bool to indicate early stopping

    :return: a model object
    """
    size, _ = next(iter(train_loader))
    size = size[1].shape[1]

    if early_stopping:
        stopping = EarlyStopping(threshold=early_stopping_threshold, verbose=True)

    wandb.watch(model)

    model.train()
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    if torch.cuda.is_available():
        model.cuda()

    counter = 0
    for e in range(epoch):
        h = model.init_hidden(size)

        for train_inputs, train_labels in train_loader:
            counter += 1

            if torch.cuda.is_available():
                train_inputs, train_labels = train_inputs.cuda(), train_labels.cuda()

            h = tuple([each.data for each in h])

            model.zero_grad()
            train_output, h = model(train_inputs, h)

            train_pred = torch.topk(train_output, k=1).indices

            train_acc, train_f1, train_pr, train_rc = _metric_summary(
                pred=train_pred.flatten().cpu().data.numpy(), label=train_labels.cpu().numpy()
            )

            train_cm = confusion_matrix(
                y_true=train_labels.cpu().numpy(), y_pred=train_pred.flatten().cpu().data.numpy()
            )

            train_figure = plot_confusion_matrix(
                train_cm, class_names=train_loader.dataset.classes
            )

            wandb.log({"Accuracy/train": train_acc}, step=counter)
            wandb.log({"F1/train": train_f1}, step=counter)
            wandb.log({"Precision/train": train_pr}, step=counter)
            wandb.log({"Recall/train": train_rc}, step=counter)
            wandb.log({"Confusion Matrix/train": train_figure}, step=counter)

            train_loss = criterion(train_output, train_labels)
            train_loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), gradient_clip)

            optimizer.step()
            wandb.log({"Loss/train": train_loss.item()}, step=counter)

            if counter % print_every == 0:
                val_h = model.init_hidden(size)
                val_losses = []
                model.eval()
                for val_inputs, val_labels in valid_loader:
                    val_h = tuple([each.data for each in val_h])

                    if torch.cuda.is_available():
                        val_inputs, val_labels = val_inputs.cuda(), val_labels.cuda()

                    val_output, val_h = model(val_inputs, val_h)
                    val_pred = torch.topk(val_output, k=1).indices

                    val_loss = criterion(val_output, val_labels)
                    val_losses.append(val_loss.item())

                    if early_stopping:
                        stopping(val_loss=val_loss, model=model)

                        if stopping.early_stop:
                            print("Early stopping")
                            break

                    val_acc, val_f1, val_pr, val_rc = _metric_summary(
                        pred=val_pred.flatten().cpu().data.numpy(), label=val_labels.cpu().numpy()
                    )

                    val_cm = confusion_matrix(
                        y_true=val_labels.cpu().numpy(), y_pred=val_pred.flatten().cpu().data.numpy()
                    )
                    val_figure = plot_confusion_matrix(
                        val_cm, class_names=train_loader.dataset.classes
                    )

                    wandb.log({"Confusion Matrix/test": val_figure}, step=counter)

                    wandb.log({"Accuracy/val": val_acc}, step=counter)
                    wandb.log({"F1/val": val_f1}, step=counter)
                    wandb.log({"Precision/val": val_pr}, step=counter)
                    wandb.log({"Recall/val": val_rc}, step=counter)

                print(
                    "Epoch: {}/{}...".format(e + 1, epoch),
                    "Step: {}...".format(counter),
                    "Training Loss: {:.6f}...".format(train_loss.item()),
                    "Validation Loss: {:.6f}".format(val_loss.item()),
                    "Train Accuracy: {:.6f}".format(train_acc),
                    "Test Accuracy: {:.6f}".format(val_acc),
                )

                model.train()

    model_name = config.GENDER_MODEL_NAME + __version__ + '.pt'
    torch.save(model.state_dict(), os.path.join(wandb.run.dir, model_name))
    return model
