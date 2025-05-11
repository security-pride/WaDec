from tree_sitter import Language, Parser, Node
import re, os
C_LANGUAGE = Language('/home/sxy/tree_sitter/build/my-languages.so', 'wat')
class WatModule:
    def __init__(self):
        self.content = ""
        # 初始化存储不同部分的列表
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
        # 定义正则表达式
        self.patterns = {}
        self.patterns["type"] = re.compile(r'(\(type \(;(\d+);\) \(func( (\(.*?\)))?\)\))')
        self.patterns["import"] = re.compile(r'(\(import \"(.*?)\" \"(.*?)\" \(func (.*?) \(type (\d+)\)\)\))')
        self.patterns["function"] = re.compile(r'  (\(func (\(;)?(.*?)(;\))? (\(type (\d+)\)( \(param .*?\))?( \(result .*?\))?).*?\))(?=\n  \()', re.DOTALL)
        self.patterns["export"] = re.compile(r'(\(export \"([\w\$]+)\" \(([\w\$]+) (.*?)\)\))')
        self.patterns["global"] = re.compile(r'(\(global ([\w\$]+) \((mut [\w\$]+)\) \((.*?)\)\))')
        self.patterns["memory"] = re.compile(r'(\(memory \(;(\d+);\) (.*?)\))')
        self.patterns["table"] = re.compile(r'(\(table \(;(\d+);\) (.*?) funcref\))')
        self.patterns["data"] = re.compile(r'(\(data (.*?) \((.*?) (\d+)\) (\".*?\"(?:\s\".*?\")*)\))')
        # self.block_pat = re.compile(r"((\s+block.*?\n)?\s+loop)")
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
        # 创建一个解析器并设置语言
        self.parser = Parser()
        self.parser.set_language(C_LANGUAGE)
    
    # ###########################################################################
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
                            # "line":line,
                            "func_type":func_type,
                            "func_signature":func_signature
                        }
                        self.sections[key][func_type] = obj
                    elif key == "import":
                        (line, import_module_name,import_func_name,func_id,func_type) = item
                        obj = {
                            # "line":line,
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
                            # "line":line,
                            "export_name":export_name,
                            "export_type":export_type,# memory or func
                            "export_id":export_id,# memry id or func name
                        }
                        self.sections[key][export_type + '$$$' + export_name] = obj
                    elif key == "global":
                        (line, global_name, mut_type, global_const) = item
                        obj = {
                            # "line":line,
                            "global_name":global_name,
                            "mut_type":mut_type,
                            "global_const":global_const
                        }
                        self.sections[key][global_name] = obj
                    elif key == "memory":
                        (line, memory_id, memory_size) = item
                        obj = {
                            # "line":line,
                            "memory_id":memory_id,
                            "memory_size":memory_size,
                        }
                        self.sections[key][memory_id] = obj
                    elif key == "table":
                        (line, table_id, table_size) = item
                        obj = {
                            # "line":line,
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
                            # "line":line,
                            "data_name":data_name,
                            "data_const_type":data_const_type,
                            "data_const":data_const_offset,
                            "data_str":data_str[1:-1],
                        }
                        self.sections[key][data_name] = obj
                break
    
    def add_func(self, func:str):
        single_function_pat = re.compile(r'(\(func (\(;)?(.*?)(;\))? (\(type (\d+)\)( \(param .*?\))?( \(result .*?\))?).*?\))$', re.DOTALL)
        match = single_function_pat.findall(func)
        if match:
            for item in match:
                (func_body,_,func_id,_,func_signature,func_type,func_param, func_result) = item
                # if func_id in ['$__original_main','$__main_argc_argv']:
                #     func_id = '$main'
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
                # 源代码中的函数都以return)结尾，但是库函数没有
                # if func_body.strip().endswith("return)") and not(func_id.startswith("$__") or func_id.startswith("$.")):
                #     self.source_func_ids.append(func_id)
    
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
    
    def divide_function2blocks_old(self,code:str, func_id:str):
        """
        以block loop划分
        """
        code = self.simplify_local_vars_dict(code)
        self.blocks[func_id] = {}
        last_start = 0
        matches = self.block_pat.finditer(code)
        for match in matches:
            start = match.start()
            temp = code[last_start:start]
            if temp.strip() != "":
                self.blocks[func_id][f"{func_id}_{len(self.blocks[func_id])}"] = temp
            last_start = start
        self.blocks[func_id][f"{func_id}_{len(self.blocks[func_id])}"] = code[last_start:]
        return self.blocks[func_id]
    
    def get_start(self,code:str,start:int):
        if start == 0:
            return 0
        # 如果是for循环，前面五航可能是参数初始化
        # i32.const 0
        # local.set 21
        # local.get 2
        # local.get 21
        # i32.store offset=96
        t = code[:start].splitlines()[-6:]
        tt= '\n'.join(t)
        m = self.var_pat.fullmatch(tt)
        # offset=\d+ 在循环中出现
        if m:
            start -= len(tt)
        else:
            start -= len(t[-1])
        return start
    
    def divide_function2blocks(self,origin_code:str, func_id:str):
        """
        以block loop划分
        """
        # if func_id in ['$__original_main','$__main_argc_argv']:
        #     func_id = '$main'
        # 函数最前面有两个空格
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
            # tree-sitter
            tree = self.parser.parse(bytes(code, "utf8"))
            # 遍历语法树，寻找函数定义
            root_node = tree.root_node
            func_node = root_node.named_children[0].named_children[0]
            self.find_loop_block(func_node)
        # block前存在变量初始化，需要修整start
        self.temp_blocks = [(self.get_start(code,start),end) for (start,end) in self.temp_blocks]
        # 对于较大的block，要删去包含的较小的block
        # replace(small_block,f"<< {small_block_id} >>", big_block)
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
        # # 检查每个block的长度是否超过最大长度
        # block_split_map = {}
        # temp_dict = self.blocks[func_id].copy()
        # for block_id, block_str in self.blocks[func_id].items():
        #     if len(block_str) > self.max_block_str_len:
        #         splite_blocks = self.split_block(block_str)
        #         if splite_blocks:
        #             block_split_map[block_id] = splite_blocks
        return self.blocks[func_id]
    def divide_function2small_blocks(self,origin_code:str, func_id:str):
        # if func_id in ['$__original_main','$__main_argc_argv']:
        #     func_id = '$main'
        self._block_pat = re.compile(r"((block[\s\w\;\@\=]*\n)?\s+(block|loop))")
        """
        以block loop划分
        """
        # 函数最前面有两个空格
        origin_code = self.simplify_local_vars_dict(origin_code)
        code = origin_code.strip()
        small_blocks = {}
        self.temp_block_starts = []
        self.temp_blocks = [(0,len(code))]
        matches = self._block_pat.finditer(code)
        for match in matches:
            if match.group(2):
                start = match.start()
            else:
                start = match.start(3)
            self.temp_block_starts.append(start)
        if self.temp_block_starts:
            # tree-sitter
            tree = self.parser.parse(bytes(code, "utf8"))
            # 遍历语法树，寻找函数定义
            root_node = tree.root_node
            func_node = root_node.named_children[0].named_children[0]
            self.find_loop_block(func_node)
        # block前存在变量初始化，需要修整start
        self.temp_blocks = [(self.get_start(code,start),end) for (start,end) in self.temp_blocks]
        # 对于较大的block，要删去包含的较小的block
        # replace(small_block,f"<< {small_block_id} >>", big_block)
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
            small_blocks[f"{func_id}_{i}"] = temp_code
        # 检查每个block的长度是否超过最大长度
        temp_list = list(small_blocks.items())
        for block_id, block_str in small_blocks.items():
            if len(block_str) > self.max_block_str_len:
                split_blocks = self.split_block(block_str)
                if split_blocks:
                    index = temp_list.index((block_id,block_str))
                    for i, split_block in enumerate(split_blocks):
                        temp_list.insert(index+i,(f'{block_id}_{i}',split_block))
                    del temp_list[index + len(split_blocks)]
        return dict(temp_list)
    # 可以用来切割没有循环的代码段的标识：
    # 1. block block (if ...)
    # 2. 函数调用和drop
    # 3. << {block_id} >>
    # 一次只切成两部分
    def split_block(self,block_id:str, block_code:str):
        pat_call = re.compile(r'\s+call ([\S\$]+)[\)\n]+((\s+drop\n)*|(local.set \d+))')
        # pat_block_id = re.compile(r'\s+<< [\S\$]+\_\d+ >>\n')
        pat_block_block = re.compile(r"(\s+)block[\s\w\;\@\=]*\n(\s+)block.*?\2end\n.*?\1end\n")
        # pat_block_block = re.compile(r"(\s+)block[\s\w\;\@\=]*(\s+)block.*?\2end\n.*?\1end\n")
        # pats = [pat_block_id,pat_block_block,pat_call]
        matches = pat_block_block.finditer(block_code)
        if_blocks = [] 
        for match in matches:
            if_blocks.append((match.start(), match.end()))
        max_len = 0
        optimal_start = 0
        optimal_end = len(block_code) - 1
        # 有 if 先切 if
        if if_blocks:
            # 找到end2, start1,使得end2-start1最大且小于2000，且start2 > end1，最后得到[start1:end2]
            if len(if_blocks) == 1:
                optimal_start, optimal_end = if_blocks[0]
                new_block = block_code[optimal_start:optimal_end]
                return [ 
                    block_code.replace(new_block, f'<< {block_id}_1 >>'),
                    new_block
                ]
            for i in range(len(if_blocks)):
                for j in range(i, len(if_blocks)):
                    start1, end1 = if_blocks[i]
                    start2, end2 = if_blocks[j]
                    if start2 < end1:
                        continue
                    distance = end2 - start1
                    # Ensure the distance is the largest found but less than 2000
                    if distance < self.max_block_str_len and distance > max_len:
                        max_len = distance
                        optimal_start = start1
                        optimal_end = end2
                # Now that we have the optimal start and end, perform the split
                new_block = block_code[optimal_start:optimal_end]
                return [
                    block_code.replace(new_block, f'<< {block_id}_1 >>'),
                    new_block
                ]
        return []
    # block_block下有instr_list
    def find_loop_block(self,block_block:Node):
        # instr_list
        # instr
        # instr_block/instr_plain
        # block_block/block_loop
        # instr_list
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
        # 单独处理函数
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
                        # "blocks" : self.divide_function2blocks(func_body,func_id),
                    }
                }
                self.sections["function"][func_id] = obj
                # 源代码中的函数都以return)结尾，但是库函数没有
                if func_body.strip().endswith("return)") and not(func_id.startswith("$__") or func_id.startswith("$.")):
                    self.source_func_ids.append(func_id)
        rest_wat_content = function_pat.sub("", wat_content)
        # 其余都是一行一行的
        for line in rest_wat_content.splitlines():
            self.add_line(line)
    
    # 从调用关系来找到树的根，这个根通常是main，不考虑有多棵树
    def get_root_from_source_funcs(self):
        call_flow = {}
        temp = ""
        for func_id in self.source_func_ids:
            for call_func_id in self.get_func_calls(func_id):
                call_flow[call_func_id] = func_id
        for func_id in self.source_func_ids:
            # 对每一个func_id找到root
            while(func_id in call_flow.keys()):
                func_id = call_flow[func_id]
            if temp == "":
                temp = func_id
            elif temp != func_id:
                print("There are more than one root in source functions!")
                return
        self.main_func_id = temp
        return self.main_func_id
             
    def get_func_calls(self,func_id:str):
        pat_call = re.compile(r'    call ([\S\$]+)[\)\n]+')
        return pat_call.findall(self.sections["function"][func_id]["func_body"])
    
    def get_source_func_calls(self,func_id:str):
        pat_call = re.compile(r'    call ([\S\$]+)[\)\n]+')
        match = pat_call.findall(self.sections["function"][func_id]["func_body"])
        return [i for i in match if i in self.source_func_ids]
    
    def get_all_funcs(self):
        all_funcs = {}
        for func_id, item in self.sections["function"].items():
            all_funcs[func_id] = item["func_body"]
        return all_funcs
    
    def find_func_globals(self,func_id:str):
        pat_global_use = re.compile(r'    global.([\w\$]+) (.*?)(\n|\))')
        matches = pat_global_use.findall(self.sections["function"][func_id]["func_body"])
        if not matches:
            return []
        return [global_name for _,global_name,_ in matches]
    
    def get_type_line(self, id):
        item = self.sections["type"][id]
        func_type = item["func_type"]
        func_signature = item["func_signature"]
        if func_signature == "":
            return f"(type (;{func_type};) (func))"
        return f"(type (;{func_type};) (func {func_signature}))"
    
    def get_import_line(self, id):
        item = self.sections["import"][id]
        import_module_name = item["import_module_name"]
        import_func_name = item["import_func_name"]
        func_id = item["func_id"]
        func_type = item["func_type"]
        return f"(import \"{import_module_name}\" \"{import_func_name}\" (func {func_id} (type {func_type})))"
    
    def get_function_body(self,id):
        item = self.sections["function"][id]
        func_body = item["func_body"]
        return func_body
    
    def get_export_line(self,id):
        item = self.sections["export"][id]
        export_name = item["export_name"]
        export_type = item["export_type"]
        export_id = item["export_id"]
        return f"(export \"{export_name}\" ({export_type} {export_id}))"
        
    def get_global_line(self, id):
        if id == '$__stack_pointer':
            return '(global $__stack_pointer (mut i32) (i32.const 65536))'
        item = self.sections["global"][id]
        global_name = item["global_name"]
        mut_type = item["mut_type"]
        global_const = item["global_const"]
        return f"(global {global_name} ({mut_type}) ({global_const}))"
    
    def get_memory_line(self, id):
        item = self.sections["memory"][id]
        memory_id = item["memory_id"]
        memory_size = item["memory_size"]
        return f"(memory (;{memory_id};) {memory_size})"
    
    def get_table_line(self, id ):
        item = self.sections["table"][id]
        table_id = item["table_id"]
        table_size = item["table_size"]
        return f"(table (;{table_id};) {table_size} funcref)"
    
    def get_data_line(self,id):
        item = self.sections["data"][id]
        data_name = item["data_name"]
        data_const = item["data_const"]
        data_const_type = item["data_const_type"]
        data_str = item["data_str"]
        return f"(data {data_name} ({data_const_type} {data_const}) \"{data_str}\")"
        
    def __str__(self):
        wat_str = "(module\n"
        for key, section in self.sections.items():
            ids = section.keys()
            for id in ids:
                if key == "type":
                    part = self.get_type_line(id)
                elif key == "import":
                    part = self.get_import_line(id)
                elif key == "function":
                    part = self.get_function_body(id)
                elif key == "table":
                    part = self.get_table_line(id)
                elif key == "memory":
                    part = self.get_memory_line(id)
                elif key == "global":
                    part = self.get_global_line(id)
                elif key == "export":
                    part = self.get_export_line(id)
                elif key == "data":
                    part = self.get_data_line(id)
                wat_str += f"  {part}\n"
                
        wat_str += ")"
        return wat_str
    def get_wat_structure(self):
        # 打印出 WAT 文件的结构
        for key, section in self.sections.items():
            print(key)
            for i in section.values():
                if key == "function":
                    i = i["attr"]
                print("  ",i)
    ####################################################################
    def get_source_wat(self,source_func_ids:list, main_id:str = ""):
        if '$main' in source_func_ids:
            if "$main" in self.sections["function"].keys():
                main_id = "$main"
            if "$__main_argc_argv" in self.sections["function"].keys():
                main_id = "$__main_argc_argv"
                
            elif "$__original_main" in self.sections["function"].keys():
                main_id = "$__original_main"
        temp_source_func_ids = []
        for i in source_func_ids:
            if i == "$main":
                temp_source_func_ids.append(main_id)
            else:
                temp_source_func_ids.append(i)
        source_func_ids = temp_source_func_ids
        self.source_func_ids = source_func_ids
        self.main_func_id = main_id
        new_module = WatModule()
        new_module.source_func_ids = self.source_func_ids
        new_module.main_func_id = self.main_func_id
        old_Sections = self.sections
        have_joined_func_type = {}
        # 先处理import函数
        for source_func_id in source_func_ids:
            func = old_Sections["function"][source_func_id]
            func_body = func["func_body"]
            func_id = func["attr"]["func_id"]
            func_type = func["attr"]["func_type"]
            new_type_sec = new_module.sections["type"]
            # 生成 import
            for call_func_id in self.get_func_calls(func_id):
                if call_func_id not in source_func_ids \
                    and call_func_id not in new_module.sections["import"].keys(): 
                    if call_func_id in old_Sections["import"].keys():
                        old_call_func_type = old_Sections["import"][call_func_id]["func_type"]      
                    else:
                        old_call_func_type = old_Sections["function"][call_func_id]["attr"]["func_type"]
                    if old_call_func_type in have_joined_func_type.keys():
                        call_func_type = have_joined_func_type[old_call_func_type]
                    else:
                        call_func_type = len(new_type_sec)
                        have_joined_func_type[old_call_func_type] = call_func_type
                        line = self.get_type_line(old_call_func_type)
                        new_module.add_line(line.replace(f';{old_call_func_type};',f';{call_func_type};'))
                    line = f"(import \"sxysxy\" \"{call_func_id}\" (func {call_func_id} (type {call_func_type})))"
                    new_module.add_line(line)
        # 后处理source函数
        for source_func_id in source_func_ids:
            func = old_Sections["function"][source_func_id]
            func_body = func["func_body"]
            func_id = func["attr"]["func_id"]
            func_type = func["attr"]["func_type"]
            new_type_sec = new_module.sections["type"]
            ###################################################################################
            Add_type = True
            if func_type in have_joined_func_type.keys():
                new_func_type = have_joined_func_type[func_type]
                Add_type = False
            else:
                new_func_type = len(new_type_sec)
                have_joined_func_type[func_type] = new_func_type
            new_module.add_func(func_body.replace(f'type {func_type}',f'type {new_func_type}'))
            
            # 找到对应的type
            if Add_type:
                line = self.get_type_line(func_type)
                new_module.add_line(line.replace(f';{func_type};',f';{len(new_type_sec)};'))
            # 找到 global
            for global_name in self.find_func_globals(func_id):
                if global_name not in new_module.sections["global"].keys():
                    # old_Sections["global"]
                    new_module.add_line(self.get_global_line(global_name))
            
        # table 和 memory保留
        for key in old_Sections["table"].keys():
            line = self.get_table_line(key)
            new_module.add_line(line)
        for key in old_Sections["memory"].keys():
            line = self.get_memory_line(key)
            new_module.add_line(line)
        # export只要main
        if main_id:
            export_line = f"(export \"main\" (func {main_id}))"
            new_module.add_line(export_line)
        # import_keys = old_Sections["export"].keys()
        # for key in import_keys:
        #     if "main" in key or "_start" in key:
        #         line = wat_module.get_export_line(key)
        #         new_module.add_line(line)
        #         break
        # elem不要
        # data 保留
        for key in old_Sections["data"].keys():
            new_module.add_line(self.get_data_line(key))
        # new_module.sections["data"] = old_Sections["data"]
        new_module.data_const_strs = self.data_const_strs
        # new_module.check_type_id()
        return new_module
    ####################################################################
    def _get_source_wat(self,source_func_ids:list = [], main_id:str = ""):
        if not source_func_ids:
            source_func_ids = self.source_func_ids
        else:
            if "$main" in self.sections["function"].keys():
                main_id = "$main"
                if '$__original_main' in self.sections["function"].keys():
                    main_id = "$__original_main"
            elif "$main" in source_func_ids and self._start:
                _start_calls = self.get_func_calls(self._start)
                main_id = _start_calls[1]
                temp = []
                for i in source_func_ids:
                    if i == "$main":
                        temp.append(main_id)
                    else:
                        temp.append(i)
                source_func_ids = temp
            self.source_func_ids = source_func_ids
        if not main_id:
            if "$main" in source_func_ids:
                self.get_root_from_source_funcs()
                main_id = self.main_func_id
        else:
            self.main_func_id = main_id
        new_module = WatModule()
        new_module.source_func_ids = self.source_func_ids
        new_module.main_func_id = self.main_func_id
        old_Sections = self.sections
        have_joined_func_type = {}
        # 先处理import函数
        for source_func_id in source_func_ids:
            func = old_Sections["function"][source_func_id]
            func_body = func["func_body"]
            func_id = func["attr"]["func_id"]
            func_type = func["attr"]["func_type"]
            new_type_sec = new_module.sections["type"]
            # 生成 import
            for call_func_id in self.get_func_calls(func_id):
                if call_func_id not in source_func_ids \
                    and call_func_id not in new_module.sections["import"].keys(): 
                    if call_func_id in old_Sections["import"].keys():
                        old_call_func_type = old_Sections["import"][call_func_id]["func_type"]      
                    else:
                        old_call_func_type = old_Sections["function"][call_func_id]["attr"]["func_type"]
                    if old_call_func_type in have_joined_func_type.keys():
                        call_func_type = have_joined_func_type[old_call_func_type]
                    else:
                        call_func_type = len(new_type_sec)
                        have_joined_func_type[old_call_func_type] = call_func_type
                        line = self.get_type_line(old_call_func_type)
                        new_module.add_line(line.replace(f';{old_call_func_type};',f';{call_func_type};'))
                    line = f"(import \"sxysxy\" \"{call_func_id}\" (func {call_func_id} (type {call_func_type})))"
                    new_module.add_line(line)
        # 后处理source函数
        for source_func_id in source_func_ids:
            func = old_Sections["function"][source_func_id]
            func_body = func["func_body"]
            func_id = func["attr"]["func_id"]
            func_type = func["attr"]["func_type"]
            new_type_sec = new_module.sections["type"]
            ###################################################################################
            Add_type = True
            if func_type in have_joined_func_type.keys():
                new_func_type = have_joined_func_type[func_type]
                Add_type = False
            else:
                new_func_type = len(new_type_sec)
                have_joined_func_type[func_type] = new_func_type
            new_module.add_func(func_body.replace(f'type {func_type}',f'type {new_func_type}'))
            
            # 找到对应的type
            if Add_type:
                line = self.get_type_line(func_type)
                new_module.add_line(line.replace(f';{func_type};',f';{len(new_type_sec)};'))
            # 找到 global
            for global_name in self.find_func_globals(func_id):
                if global_name not in new_module.sections["global"].keys():
                    # old_Sections["global"]
                    new_module.add_line(self.get_global_line(global_name))
            
        # table 和 memory保留
        for key in old_Sections["table"].keys():
            line = self.get_table_line(key)
            new_module.add_line(line)
        for key in old_Sections["memory"].keys():
            line = self.get_memory_line(key)
            new_module.add_line(line)
        # export只要main
        export_line = f"(export \"main\" (func {main_id}))"
        new_module.add_line(export_line)
        # elem不要
        # data 保留
        for key in old_Sections["data"].keys():
            new_module.add_line(self.get_data_line(key))
        # new_module.sections["data"] = old_Sections["data"]
        new_module.data_const_strs = self.data_const_strs
        # new_module.check_type_id()
        return new_module
    def get_ordered_funcs(self):
        self.source_func_names = self.source_func_ids
        #####################################################
        import numpy as np
        n = len(self.source_func_names)
        arr = np.zeros((n,n))
        for i, func_name in enumerate(self.source_func_names):
            for call_func_name in self.get_source_func_calls(func_name):
                if call_func_name not in self.source_func_names:
                    continue
                j = self.source_func_names.index(call_func_name)
                arr[i,j] = 1
        func_index_list = [i for i in range(n)]
        func_order_list = []
        while(func_index_list):
            flag = True
            for i in func_index_list:
                if sum(arr[i]) == 0:
                    flag = False
                    func_order_list.append(self.source_func_names[i])
                    func_index_list.remove(i)
                    for j in range(n):
                        arr[j,i] = 0
            if flag:
                k = func_index_list[0]
                func_order_list.append(self.source_func_names[k])
                func_index_list.remove(k)
                for j in range(n):
                    arr[j,k] = 0
        return func_order_list
    
if __name__ == "__main__":
    # 使用示例
    self = WatModule()
    # self.parse_wat("/home/sxy/wasm2c/z_test/b_test/b.wat")
    self.parse_wat('/home/sxy/wasm2c/Llm4Wat2C/1_Dataset/github_thealgorithms/original/Filted/wat/o0/alg_file190.wat')
    new_wat_module = self.get_source_wat([\
        # f"${i}" for i in ['main', 'add', 'aa', 'bb']\
        f"${i}" for i in ['moveZeroes']\
    ])
    self._block_pat(self.sections['function']['$moveZeroes']['func_body'],'$moveZeroes')
    print(new_wat_module.get_ordered_funcs())
    # data_consts = new_wat_module.get_const_strs(\
    #     new_wat_module.sections["function"]["$main"]["func_body"])
    # for i in data_consts.items():
    #     print(i)
    # # print("####################################################")
    # aaa = new_wat_module.get_offset_from_str("Hello, ") + 65536
    # print(aaa)
    # print(new_wat_module.get_str_by_offset(aaa))
