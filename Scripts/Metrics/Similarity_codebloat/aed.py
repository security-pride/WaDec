import math
import numpy
from tree_sitter import Language, Parser, Node
C_LANGUAGE = Language(f'{os.getcwd()}/Metrics/Codebleu/so/my-languages.so', 'c')
parser = Parser()
parser.set_language(C_LANGUAGE)
 
def point(x, y):
    return '[' + str(x) + ',' + str(y) + ']'
 
def traverse(node:Node):
    seq = []
    cursor = node.walk()

    while True:
        seq.append(cursor.node.type)
        if cursor.goto_first_child():
            continue
        while not cursor.goto_next_sibling():
            if not cursor.goto_parent():
                return seq
class CodeParse(object):
    def __init__(self, fileA, fileB):
        self.codeA = open(fileA, encoding="utf-8").read()
        self.codeB = open(fileB, encoding="utf-8").read()
        self.nodeA = parser.parse(bytes(self.codeA, "utf8")).root_node
        self.nodeB = parser.parse(bytes(self.codeB, "utf8")).root_node
        self.seqA = traverse(self.nodeA)
        self.seqB = traverse(self.nodeB)
 
 
class CalculateSimilarity(object):
    def __init__(self, A, B, W, M, N,identifier_weight = 0.5):
        self.A = A
        self.B = B
        self.W = W
        self.M = M
        self.N = N
        self.identifier_weight = identifier_weight
        self.similarity = []
        self.SimthWaterman(self.A, self.B, self.W)
 
    def score(self,a, b):
        if a == b:
            return self.M
        else:
            return self.N
 
    def traceback(self,A, B, H, path:dict, value:list, result:list):
        if value:
            temp = value[0]
            result.append(temp)
            value = path[temp]
            x = int((temp.split(',')[0]).strip('['))
            y = int((temp.split(',')[1]).strip(']'))
        else:
            return
        if H[x, y] == 0: 
            xx = 0
            yy = 0
            sim = 0
            for item in range(len(result) - 2, -1, -1):
                position = result[item]
                x = int((position.split(',')[0]).strip('['))
                y = int((position.split(',')[1]).strip(']'))
                if x == xx:
                    pass
                elif y == yy:
                    pass
                else:
                    sim = sim + 1
                xx = x
                yy = y
            self.similarity.append(sim * 2 / (len(A) + len(B)))
 
        else:
            self.traceback(A, B, H, path, value, result)
 
    def SimthWaterman(self, A, B, W):
        n, m = len(A), len(B)
        H = numpy.zeros([n + 1, m + 1], int)
        path = {}
        for i in range(0, n + 1):
            for j in range(0, m + 1):
                if i == 0 or j == 0:
                    path[point(i, j)] = []
                else:
                    s = self.score(A[i - 1], B[j - 1])
                    L = H[i - 1, j - 1] + s
                    P = H[i - 1, j] - W
                    Q = H[i, j - 1] - W
                    H[i, j] = max(L, P, Q, 0)
 
                    path[point(i, j)] = []
                    if math.floor(L) == H[i, j]:
                        path[point(i, j)].append(point(i - 1, j - 1))
                    if math.floor(P) == H[i, j]:
                        path[point(i, j)].append(point(i - 1, j))
                    if math.floor(Q) == H[i, j]:
                        path[point(i, j)].append(point(i, j - 1))
 
        end = numpy.argwhere(H == numpy.max(H))
        for pos in end:
            key = point(pos[0], pos[1])
            value = path[key]
            result = [key]
            self.traceback(A, B, H, path, value, result)
 
    def Answer(self):
        return sum(self.similarity) / len(self.similarity)
 
 
def get_AED_SCORE(original_path,decompiled_path):
    AST = CodeParse(original_path,decompiled_path)
    RES = CalculateSimilarity(AST.seqA, AST.seqB, 1, 1, -1/3)
    return RES.Answer()
 
if __name__ == "__main__":
    original_path = 'xxx_renamed.c'
    decompiled_path = 'xxx_decompiled.c'
    print(get_AED_SCORE(original_path,decompiled_path))
