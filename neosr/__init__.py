from argparse import ArgumentParser
import sys

def do_train():
  from . import train
  train.train_pipeline(".")


def main():
  parser = ArgumentParser()
  parser.add_argument("command")
  args, unknown = parser.parse_known_args()

  if args.command == "train":
    print(unknown)
    del sys.argv[1]
    do_train()
