from tree_sitter import Language, Parser, Node
import re, os
C_LANGUAGE = Language(f'{os.getcwd()}/Metrics/Codebleu/so/my-languages.so', 'wat')
class WatModule:
    def __init__(self):
        self.content = ""
        self.sections = {
            "type" : {},
            "import" : {},
            "function" : {},
            "table" : {},
            "memory" : {},
            "global" : {},
            "export" : {},
            "data" : {},
        }
        self.blocks = {}
        self.source_func_ids = []
        self.main_func_id = ""
        self._start = ""
        self.data_const_strs = {}
        self.patterns = {}
        self.patterns["type"] = re.compile(r'(\(type \(;(\d+);\) \(func( (\(.*?\)))?\)\))')
        self.patterns["import"] = re.compile(r'(\(import \"(.*?)\" \"(.*?)\" \(func (.*?) \(type (\d+)\)\)\))')
        self.patterns["function"] = re.compile(r'  (\(func (\(;)?(.*?)(;\))? (\(type (\d+)\)( \(param .*?\))?( \(result .*?\))?).*?\))(?=\n  \()', re.DOTALL)
        self.patterns["export"] = re.compile(r'(\(export \"([\w\$]+)\" \(([\w\$]+) (.*?)\)\))')
        self.patterns["global"] = re.compile(r'(\(global ([\w\$]+) \((mut [\w\$]+)\) \((.*?)\)\))')
        self.patterns["memory"] = re.compile(r'(\(memory \(;(\d+);\) (.*?)\))')
        self.patterns["table"] = re.compile(r'(\(table \(;(\d+);\) (.*?) funcref\))')
        self.patterns["data"] = re.compile(r'(\(data (.*?) \((.*?) (\d+)\) (\".*?\"(?:\s\".*?\")*)\))')
        self.var_pat = re.compile(
            r"\s+[if]\d+\.const\s+\d+\n"
            r"\s+local\.set\s+(\d+)\n"
            r"\s+local\.get\s+\d+\n"
            r"\s+local\.get\s+\1\n"
            r"\s+[if]\d+\.store(?:\d+)?\s+(offset=\d+)"
            r"\s+"
        )
        self.block_pat = re.compile(r"((block[\s\w\;\@\=]*\n)?\s+(loop))")
        self.local_x = re.compile(r'\(local (.*)\)')
        self.const_str_pat = re.compile(r'(i\d+.const) (\d+)')
        self.trans_pat = re.compile(r'\\[0-9a-fA-F]{2}')
        self.parser = Parser()
        self.parser.set_language(C_LANGUAGE)
    
    def add_line(self, line:str):
        if line.startswith("(module"):
            return
        for key, pat in self.patterns.items():
            if key == "function":
                continue
            match = pat.findall(line)
            if match:
                for item in match:
                    if key == "type":
                        (line, func_type,_ , func_signature) = item
                        obj = {
                            "func_type":func_type,
                            "func_signature":func_signature
                        }
                        self.sections[key][func_type] = obj
                    elif key == "import":
                        (line, import_module_name,import_func_name,func_id,func_type) = item
                        obj = {
                            "import_module_name":import_module_name,
                            "import_func_name":import_func_name,
                            "func_id":func_id,
                            "func_type":func_type
                        }
                        self.sections[key][func_id] = obj
                    elif key == "export":
                        (line, export_name,export_type,export_id) = item
                        if export_name == "_start":
                            self._start = export_id
                        obj = {
                            "export_name":export_name,
                            "export_type":export_type,# memory or func
                            "export_id":export_id,# memry id or func name
                        }
                        self.sections[key][export_type + '$$$' + export_name] = obj
                    elif key == "global":
                        (line, global_name, mut_type, global_const) = item
                        obj = {
                            "global_name":global_name,
                            "mut_type":mut_type,
                            "global_const":global_const
                        }
                        self.sections[key][global_name] = obj
                    elif key == "memory":
                        (line, memory_id, memory_size) = item
                        obj = {
                            "memory_id":memory_id,
                            "memory_size":memory_size,
                        }
                        self.sections[key][memory_id] = obj
                    elif key == "table":
                        (line, table_id, table_size) = item
                        obj = {
                            "table_id":table_id,
                            "table_size":table_size,
                        }
                        self.sections[key][table_id] = obj
                    elif key == "data":
                        (line, data_name, data_const_type, data_const_offset, data_str) = item
                        if data_const_type not in self.data_const_strs.keys():
                            self.data_const_strs[data_const_type] = [(data_name,data_const_offset,data_str[1:-1])]
                        else:
                            self.data_const_strs[data_const_type].append((data_name,data_const_offset,data_str[1:-1]))
                        obj = {
                            "data_name":data_name,
                            "data_const_type":data_const_type,
                            "data_const":data_const_offset,
                            "data_str":data_str[1:-1],
                        }
                        self.sections[key][data_name] = obj
                break
    def get_offset_from_str(self,string:str):
        pat = re.compile(r'\\[0-9a-fA-F]{2}')
        string = string.replace('\n','\\0a') + '\\00'
        s = ""
        for _, item in self.sections["data"].items():
            data_str = item["data_str"]
            if string in data_str:
                i = data_str.find(string)
                s = data_str[:i]
                break
        offset = 0
        j = 0
        while(j < len(s)):
            if pat.fullmatch(s[j:j+3]):
                j += 3
            else:
                j += 1
            offset += 1
        return offset
    
    def get_str_by_offset(self,const_offset:int):
        pat = re.compile(r'\\[0-9a-fA-F]{2}')
        data = ""
        for _, items in self.data_const_strs.items():
            for _, dataseg_start, data_str in items:
                dataseg_start = int(dataseg_start)
                if dataseg_start + len(data_str) > const_offset >= dataseg_start:
                    offset = const_offset - dataseg_start
                    j = 0
                    for _ in range(offset):
                        if pat.fullmatch(data_str[j:j+3]):
                            j += 3
                        else:
                            j += 1
                    strlength = data_str[j:].find('\\00')
                    data = data_str[j:j+strlength]
                    break
        return data
    def simplify_local_vars_dict(self,func:str):
        match = self.local_x.search(func)
        var_dict = {}
        if match:
            for item in match.group(1).split(" "):
                if item not in var_dict.keys():
                    var_dict[item] = 0
                else:
                    var_dict[item] += 1
            return func.replace(match.group(0) ,str(var_dict))
        return func
    
    def get_const_strs(self,code:str):
        strs = {}
        pat = self.trans_pat
        matches = self.const_str_pat.findall(code)
        if matches:
            for const_type, const_offset in matches:
                const_offset = int(const_offset)
                if const_type not in self.data_const_strs.keys():
                    continue
                for dataseg_name,dataseg_start, data_str in self.data_const_strs[const_type]:
                    dataseg_start = int(dataseg_start)
                    if dataseg_start + len(data_str) > const_offset >= dataseg_start:
                        offset = const_offset - dataseg_start
                        i = 0
                        for _ in range(offset):
                            if pat.fullmatch(data_str[i:i+3]):
                                i += 3
                            else:
                                i += 1
                        strlength = data_str[i:].find('\\00')
                        data = data_str[i:i+strlength]
                        strs[f'{dataseg_name} ({const_type} {const_offset})'] = data
                        break
        return strs
    
    def get_start(self,code:str,start:int):
        if start == 0:
            return 0
        t = code[:start].splitlines()[-6:]
        tt= '\n'.join(t)
        m = self.var_pat.fullmatch(tt)
        if m:
            start -= len(tt)
        else:
            start -= len(t[-1])
        return start
    
    def divide_function2blocks(self,origin_code:str, func_id:str):
        origin_code = self.simplify_local_vars_dict(origin_code)
        code = origin_code.strip()
        self.blocks[func_id] = {}
        self.temp_block_starts = []
        self.temp_blocks = [(0,len(code))]
        matches = self.block_pat.finditer(code)
        for match in matches:
            if match.group(2):
                start = match.start()
            else:
                start = match.start(3)
            self.temp_block_starts.append(start)
        if self.temp_block_starts:
            tree = self.parser.parse(bytes(code, "utf8"))
            root_node = tree.root_node
            func_node = root_node.named_children[0].named_children[0]
            self.find_loop_block(func_node)
        self.temp_blocks = [(self.get_start(code,start),end) for (start,end) in self.temp_blocks]
        for i, (start, end) in enumerate(self.temp_blocks):
            temp_code = code[start:end]
            sub_start = sub_end = start
            sub_id = None
            for j, (st, ed) in enumerate(self.temp_blocks[i+1:]):
                if st > end:
                    break
                if sub_start == sub_end:
                    sub_start = st
                    sub_end = ed
                    sub_id = i + 1 + j
                elif st > sub_end:
                    temp_code = temp_code.replace(code[sub_start:sub_end].strip(),f"<< {f'{func_id}_{sub_id}'} >>")
                    sub_start = st
                    sub_end = ed
                    sub_id = i + 1 + j
            if sub_id:
                temp_code = temp_code.replace(code[sub_start:sub_end].strip(),f"<< {f'{func_id}_{sub_id}'} >>")
            pattern = rf"\n(\s*){re.escape(temp_code[:40])}"
            match = re.search(pattern,origin_code)
            if match:
                temp_code = match.group(1) + temp_code
            self.blocks[func_id][f"{func_id}_{i}"] = temp_code
        return self.blocks[func_id]

    def find_loop_block(self,block_block:Node):
        instr_list = None
        for node in block_block.named_children:
            if node.type == "instr_list":
                instr_list = node
        if not instr_list:
            return
        for instr in instr_list.named_children:
            if instr.named_children[0].type == "instr_block":
                pass
            if instr.start_byte<= self.temp_block_starts[0] < instr.end_byte and instr.named_children[0].type == "instr_block":
                instr_block = instr.named_children[0]
                if instr.start_byte == self.temp_block_starts[0]:
                    self.temp_blocks.append((instr.start_byte,instr.end_byte))
                    if len(self.temp_block_starts) == 1:
                        return
                    else:
                        self.temp_block_starts = self.temp_block_starts[1:]
                for b in instr_block.named_children:
                    if b.type in ["block_block","block_loop"]:
                        block = b
                        break
                if block.start_byte <= self.temp_block_starts[0] < block.end_byte:
                    self.find_loop_block(block)
        return
    
    def parse_wat(self, wat_source, max_block_str_len = 2000):
        self.max_block_str_len = max_block_str_len
        if isinstance(wat_source, str) and os.path.isfile(wat_source):
            with open(wat_source, 'r') as file:
                wat_content = file.read()
        else:
            wat_content = wat_source
        self.content = wat_content
        function_pat = self.patterns["function"]
        matches = function_pat.findall(wat_content)
        if matches:
            for item in matches:
                (func_body,_,func_id,_,func_signature,func_type,func_param, func_result) = item
                obj = {
                    "func_body":func_body,
                    "attr": {
                        "func_id":func_id,
                        "func_signature":func_signature,
                        "func_type":func_type,
                        "func_param":func_param,
                        "func_result":func_result,
                        "blocks" : self.divide_function2blocks(func_body,func_id),
                    }
                }
                self.sections["function"][func_id] = obj
                if func_body.strip().endswith("return)") and not(func_id.startswith("$__") or func_id.startswith("$.")):
                    self.source_func_ids.append(func_id)
        rest_wat_content = function_pat.sub("", wat_content)
        for line in rest_wat_content.splitlines():
            self.add_line(line)

    def get_source_func_calls(self,func_id:str):
        pat_call = re.compile(r'    call ([\S\$]+)[\)\n]+')
        match = pat_call.findall(self.sections["function"][func_id]["func_body"])
        return [i for i in match if i in self.source_func_ids]
    
    def get_ordered_funcs(self, invoke_list:list[str]):
        import numpy as np
        n = len(invoke_list)
        arr = np.zeros((n,n))
        for i, func_name in enumerate(invoke_list):
            for call_func_name in self.get_source_func_calls(func_name):
                if call_func_name not in invoke_list:
                    continue
                j = invoke_list.index(call_func_name)
                arr[i,j] = 1
        func_index_list = [i for i in range(n)]
        func_order_list = []
        while(func_index_list):
            flag = True
            for i in func_index_list:
                if sum(arr[i]) == 0:
                    flag = False
                    func_order_list.append(invoke_list[i])
                    func_index_list.remove(i)
                    for j in range(n):
                        arr[j,i] = 0
            if flag:
                k = func_index_list[0]
                func_order_list.append(invoke_list[k])
                func_index_list.remove(k)
                for j in range(n):
                    arr[j,k] = 0
        return func_order_list
    
