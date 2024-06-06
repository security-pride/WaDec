import json, os, re
import subprocess
from formatting import formated_c
from codebleu import calc_codebleu
import argparse
def Calc_codebleu(reference:str, prediction:str, lang = 'c', weights = (0.25, 0.25, 0.25, 0.25)):
    if os.path.exists(reference):
        reference = open(reference).read()
    if os.path.exists(prediction):
        prediction = open(prediction).read()
    return calc_codebleu(
            [formated_c(reference)], 
            [formated_c(prediction)], 
            lang=lang, 
            weights=weights, 
            tokenizer=None
        )['codebleu']

def parse_arguments():
    parser = argparse.ArgumentParser(description='Calculate CodeBLEU score between reference and prediction code.')
    parser.add_argument('reference', type=str, help='Path to the reference code file or the reference code itself')
    parser.add_argument('prediction', type=str, help='Path to the prediction code file or the prediction code itself')
    parser.add_argument('--lang', type=str, default='c', choices=['c', 'cpp', 'java', 'python'], help='Programming language of the code (default: c)')
    parser.add_argument('--weights', type=float, nargs=4, default=[0.25, 0.25, 0.25, 0.25], help='Weights for n-gram precisions (default: 0.25 0.25 0.25 0.25)')
    return parser.parse_args()

def main():
    args = parse_arguments()
    codebleu_score = Calc_codebleu(args.reference, args.prediction, lang=args.lang, weights=args.weights)
    print(f'CodeBLEU score: {codebleu_score}')

if __name__ == '__main__':
    main()