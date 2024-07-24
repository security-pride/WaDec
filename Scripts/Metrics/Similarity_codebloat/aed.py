import re
from apted import APTED,PerEditOperationConfig
from apted.helpers import Tree
from tree_sitter import Language, Parser, Node


class Node:
    def __init__(self, name, path):
        self.id = path
        self.name = name
        self.children = []

    def add_child(self, node):
        self.children.append(node)
def parse_tree_string(tree_string):
    stack = []
    current_node = None
    tokens = tree_string.replace('(', ' ( ').replace(')', ' ) ').split()

    for token in tokens:
        if token == '(':
            if current_node is not None:
                stack.append(current_node)
            current_node = Node("", "")
        elif token == ')':
            if stack:
                parent_node = stack.pop()
                parent_node.add_child(current_node)
                current_node = parent_node
            else:
                # Extra closing parenthesis, ignore it
                continue
        else:
            # Use the content between brackets as the node name
            name = token.strip('()')
            if current_node is None:
                current_node = Node("", "")
            if name!="":
                # if ":" in name:
                #     name=name.split(":")[0]
                current_node.name = name
            else: current_node.name = " "

    return current_node
def calculate_node_count(node):
    """Calculate the number of nodes in the tree."""
    count = 1  # Count the current node

    # Recursively calculate the number of nodes for each child
    for child in node.children:
        count += calculate_node_count(child)

    return count

def get_Trees(lan,origin,target):
    C_LANGUAGE = Language('xxx/tree_sitter/build/my-languages.so', 'c')
    parser = Parser()
    parser.set_language(C_LANGUAGE)
    tree1 = parser.parse(bytes(origin, encoding='UTF-8'))
    tree2 = parser.parse(bytes(target, encoding='UTF-8'))
    tree1_str=tree1.root_node.sexp()
    tree2_str=tree2.root_node.sexp()
    len1=str(tree1_str).count(")")
    len2=str(tree2_str).count(")")
    tree_origin=parse_tree_string(tree1_str)
    tree_target=parse_tree_string(tree2_str)
    return tree_origin,tree_target,max(len1,len2)

def Calaulte(lan,str1,str2,d,i,r):
    
    tree1,tree2,max_len=get_Trees(lan,str1,str2)
    apted = APTED(tree1, tree2,PerEditOperationConfig(d, i, r))
    res = apted.compute_edit_distance()
    if max_len>0:
        if res>max_len:
            return(0.0)
        else : return((max_len-res)/max_len) 
    else: return(1.0)

def get_AED_SCORE(original_path,decompiled_path):
    RES = Calaulte(
       'c',
       open(original_path).read(),
       open(decompiled_path).read(), 
       1.0, 
       0.8, 
       1.0
    )
    return RES
