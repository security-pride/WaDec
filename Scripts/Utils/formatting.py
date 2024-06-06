import re, os, sys
from tree_sitter import Language, Parser, Node
from timeout_decorator import timeout, TimeoutError
C_LANGUAGE = Language(f'{os.getcwd()}/Metrics/Codebleu/so/my-languages.so', 'c')
parser = Parser()
parser.set_language(C_LANGUAGE)
commentlines_pat = re.compile(r'/\*.*?\*/', flags=re.DOTALL)
commentline_pat = re.compile(r'\s*//.*')
blankline_pat = re.compile(r'\n\s*\n')
init_pat = re.compile(r'\b(\w+)\s+([\w_]+);\s+\2\s*=\s*(.+?);')
local_pat = re.compile(r'\b(local\_\d+)\b')
const_pat = re.compile(r'\bconst\s+')
@timeout(0.2)
def convert_initialization(code):
    def simplify_func(func_body:str):
        local_vars_count = {}
        matches = local_pat.findall(func_body)
        if not matches:
            return code
        for match in matches:
            local_var = match
            if local_var in local_vars_count.keys():
                local_vars_count[local_var] += 1
            else:
                local_vars_count[local_var] = 1
        for var_name, count in local_vars_count.items():
            if count == 1:
                local_init_pat = re.compile(rf'(\s*[\w\_]+( local\_\d+,)* ({var_name}).*?([,;]))')
                matches = local_init_pat.findall(func_body)
                if not matches:
                    continue
                for match in matches:
                    if match[1] or match[3] == ',':
                        func_body = func_body.replace(f' {var_name},','')
                    else:
                        func_body = func_body.replace(match[0],'')
            # elif count == 2:
            #     local_declaration_pat = re.compile(rf'[\w\_]+(\s*local\_\d+(\s*=.*)?,)*( {var_name}[,;])')
            #     local_init_pat = re.compile(rf' \s*{var_name} = .*?[,;]')
            #     match1 = local_declaration_pat.search(func_body)
            #     match2 = local_init_pat.search(func_body)
            #     if not match1 or not match2:
            #         continue
            #     func_body = func_body.replace(match2.group(),'')
            #     func_body = func_body.replace(match1.group(3)[:-1],match2.group()[:-1])
        return func_body
    tree = parser.parse(bytes(code, "utf8"))
    res = []
    for node in tree.root_node.named_children:
        text = node.text.decode()
        if not node.has_error and node.type == 'function_definition':
            text = (simplify_func(text))
        res.append(text)
    return '\n'.join(res)
def formated_c(code):
    code = commentline_pat.sub('\n',code)
    code = commentlines_pat.sub('\n',code)
    code = blankline_pat.sub('\n\n',code)
    code = const_pat.sub('',code)
    code = convert_initialization(code)
    code = blankline_pat.sub('\n\n',code)
    return code.strip()