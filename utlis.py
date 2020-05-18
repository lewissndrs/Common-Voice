from __future__ import unicode_literals

import itertools
import os
import shutil

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import tqdm
from pydub import AudioSegment

from model.config import config


def csv_loader(path: str) -> torch.Tensor:
    """
    :param path:
    :return:
    """
    data = np.array(pd.read_csv(path, header=None))
    sample = torch.from_numpy(data)
    return sample


def mp3_loader(path):
    file = AudioSegment.from_mp3(path)
    return file


def envelope(*, y: object, signal_rate: object, threshold: object):
    signal_clean = []
    y = pd.Series(y).apply(np.abs)
    y_mean = y.rolling(
        window=int(signal_rate / 1000), min_periods=1, center=True
    ).mean()

    for mean in y_mean:
        if mean > threshold:
            signal_clean.append(True)
        else:
            signal_clean.append(False)
    return signal_clean


def remove_un_label_files(clips_names: list) -> None:
    """
    Remove a list of list of files that do not contain any labels
    :param clips_names: list of of mp3 names

    """
    data = pd.read_csv("Development/data.csv")
    data_path = set(data.path)
    clips_path = config.LocalStorage.CLIPS_DIR

    delete_path = r"C:\Users\ander\Documents\delete"

    for mp3 in tqdm(clips_names):
        if mp3 not in data_path:
            shutil.move(os.path.join(clips_path, mp3), os.path.join(delete_path, mp3))


def calc_fft(*, y, rate):
    n = len(y)
    freq = np.fft.rfftfreq(n, d=1 / rate)
    Y = abs(np.fft.rfft(y) / n)

    return Y, freq


def plot_confusion_matrix(cm: np.ndarray, class_names: list) -> matplotlib.figure.Figure:
    """
    Generates a Matplotlib figure containing the plotted confusion matrix.

    :param cm: cm (array, shape = [n, n]): a confusion matrix of integer classes
    :param class_names: class_names (array, shape = [n]): String names of the integer classes
    :return:
  """
    figure = plt.figure(figsize=(8, 8))
    plt.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    plt.title("Confusion matrix")
    plt.colorbar()
    tick_marks = np.arange(len(class_names))
    plt.xticks(tick_marks, class_names, rotation=45)
    plt.yticks(tick_marks, class_names)

    # Normalize the confusion matrix.
    cm = np.around(cm.astype("float") / cm.sum(axis=1)[:, np.newaxis], decimals=2)

    # Use white text if squares are dark; otherwise black.
    threshold = cm.max() / 2.0
    for i, j in itertools.product(range(cm.shape[0]), range(cm.shape[1])):
        color = "white" if cm[i, j] > threshold else "black"
        plt.text(j, i, cm[i, j], horizontalalignment="center", color=color)

    plt.tight_layout()
    plt.ylabel("True label")
    plt.xlabel("Predicted label")
    return figure
