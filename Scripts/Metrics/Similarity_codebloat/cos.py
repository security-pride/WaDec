from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re
commentlines_pat = re.compile(r'/\*.*?\*/', flags=re.DOTALL)
commentline_pat = re.compile(r'\s*//.*')
blankline_pat = re.compile(r'\n\s*\n')
def remove_comments_and_empty_lines(code):
    code = commentline_pat.sub('\n',code)
    code = commentlines_pat.sub('\n',code)
    code = blankline_pat.sub('\n',code)
    return '\n'.join([i for i in code.strip() if not i.startswith('#')])

def get_COS_SCORE(original_path,decompiled_path):
    with open(original_path,'r') as f1:
        code1 = remove_comments_and_empty_lines(f1.read())
    with open(decompiled_path,'r') as f2:
        code2 = remove_comments_and_empty_lines(f2.read())

    vectorizer = CountVectorizer(token_pattern=r"(?u)\b\w+\b")
    vectors = vectorizer.fit_transform([code1, code2]).toarray()
    similarity = cosine_similarity([np.array(vectors[0])], [np.array(vectors[1])])[0][0]
    return similarity

if __name__ == '__main__':
    original_path = 'xxx_renamed.c'
    decompiled_path = 'xxx_decompiled.c'
    get_COS_SCORE(original_path,decompiled_path)
