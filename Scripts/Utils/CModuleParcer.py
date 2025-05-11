from tree_sitter import Language, Parser, Node
import numpy as np
import re, os
cur = os.path.abspath(__file__)
dir_path = os.path.dirname(cur)
C_LANGUAGE = Language(f'{dir_path}/so/my-languages.so', 'c')
parser = Parser()
parser.set_language(C_LANGUAGE)
# import tree_sitter_c
# C_LANGUAGE = Language(tree_sitter_c.language())
# parser = Parser(C_LANGUAGE)
class CModule:
    def __init__(self,c_content = "") -> None:
        self.functions = {}
        self.pat = re.compile(r"\(\".*?\"(\s*,\s*[_\w]+)*\)")
        self.blocks = {}
        self.not_called = []
        if c_content:
            if os.path.exists(c_content):
                with open(c_content,'r') as f:
                    c_content = f.read()
            self.parcer_c(c_content)
            
    def find_string_literals(self,node):
        literals = []
        if node.type == 'string_literal':
            string = node.text.decode('utf-8')
            literals.append(string)
        for child in node.children:
            literals.extend(self.find_string_literals(child))
        return literals

    def str_sort(self, string_list:list[str]):
        return sorted(string_list, key=lambda x: len(x), reverse=True)
    
    def find_while_statements(self, node:Node, function_name:str):
        if node.type in ["while_statement","for_statement","do_statement"]:
            self.temp_blocks.append((node.start_byte,node.end_byte))           
        for child in node.children:
            self.find_while_statements(child,function_name)
        return
    
    def create_pattern_for_n_parameters(self,name:str,n:int):
        param_pattern = r"\s*([\w_\+\-\*/\(\)]+)\s*"
        full_pattern = param_pattern + (rf",{param_pattern}") * (n - 1)
        return rf"\b({name}\({full_pattern}\))"
    
    def replace_defines(self,code:str):
        text = code
        tree = parser.parse(bytes(code, "utf8"))
        for node in tree.root_node.named_children:
            if node.type == "preproc_def":
                def_str = code[node.start_byte:node.end_byte]
                text = text.replace(def_str,"")
                old_str = ""
                new_str = ""
                for child in node.named_children:
                    if child.type == "identifier":
                        old_str = child.text.decode('utf-8')
                        old_str = fr"\b{old_str}\b"
                    elif child.type == "preproc_arg":
                        new_str = child.text.decode('utf-8')
                if not new_str:
                    return self.replace_defines(text)
                text = re.sub(old_str,new_str,text)
                return self.replace_defines(text)
            elif node.type == "preproc_function_def":
                def_str = code[node.start_byte:node.end_byte]
                text = text.replace(def_str,"")
                for child in node.named_children:
                    if child.type == "identifier":
                        name = child.text.decode('utf-8')
                    elif child.type == "preproc_params":
                        param_node = child
                    elif child.type == "preproc_arg":
                        value = child.text.decode('utf-8')
                params = []
                params_dict = {}
                for child_node in param_node.named_children:
                    if child_node.type == "identifier":
                        params.append(code[child_node.start_byte:child_node.end_byte])
                pattern = self.create_pattern_for_n_parameters(name,len(params))
                pat = re.compile(pattern)
                matches = pat.findall(text)
                for match in enumerate(matches):
                    match_list = []
                    for i in match[1]:
                        match_list.append(i)
                    params_dict = dict(zip(params,match_list[1:]))
                    temp = value
                    for param in params:
                        temp = re.sub(rf"\b{param}\b",params_dict[param],temp)
                    text = text.replace(match_list[0], temp)
                return self.replace_defines(text)
        return text
    
    def parcer_c(self,c_code:str):
        if not c_code:
            return
        if os.path.isfile(c_code):
            with open(c_code,"r") as f:
                c_code = f.read()
        self.text = c_code
        self.func_callls = {}
        tree = parser.parse(bytes(c_code, "utf8"))
        root_node = tree.root_node
        self.root_node = root_node
        self.literals = {}
        for node in root_node.children:
            if node.type == 'function_definition':
                self.temp_blocks = [(node.start_byte,node.end_byte)]
                temp_node = node
                while(temp_node.type != "identifier"):
                    if temp_node.type == 'parenthesized_declarator':
                        temp_node = temp_node.named_children[0]
                        continue
                    temp_node = temp_node.child_by_field_name('declarator')
                    
                function_name = temp_node.text.decode('utf-8')
                function_body = c_code[node.start_byte:node.end_byte]
                func_strings = self.find_string_literals(node)
                self.literals[function_name] = func_strings
                func_strings = self.str_sort(func_strings) 
                for i in func_strings:
                    if i in function_body:
                        function_body = function_body.replace(i,'""')
                temp = []
                for i in self.find_function_calls(node):
                    if i not in temp:
                        temp.append(i)
                self.func_callls[function_name] = temp
                self.blocks[function_name] = {}
                self.last_start_byte = node.start_byte
                self.find_while_statements(node,function_name)
                code = self.text
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
                            temp_code = temp_code.replace(code[sub_start:sub_end],f"<< {f'{function_name}_{sub_id}'} >>")
                            sub_start = st
                            sub_end = ed
                            sub_id = i + 1 + j
                    if sub_id:
                        temp_code = temp_code.replace(code[sub_start:sub_end],f"<< {f'{function_name}_{sub_id}'} >>")
                    self.blocks[function_name][f"{function_name}_{i}"] = temp_code
                
                self.functions[function_name] = {
                    "func_name" : function_name,
                    "func_body" : function_body,
                    "blocks" : self.blocks[function_name],
                }
        return

    def find_function_calls(self, node):
        function_calls = []
        if node.type == 'call_expression':
            function_name_node = node.children[0]
            if function_name_node.type == 'identifier':
                func_name = function_name_node.text.decode('utf-8')
                function_calls.append(func_name)
        for child in node.named_children:
            function_calls.extend(self.find_function_calls(child))
        return function_calls
    
    def get_ordered_funcs(self):
        self.source_func_names = self.get_source_func_names()
        n = len(self.source_func_names)
        arr = np.zeros((n,n))
        for i, func_name in enumerate(self.source_func_names):
            for call_func_name in self.func_callls[func_name]:
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
    
    def get_accessable_funcs(self):
        # Step 0: Get all source function names
        all_source_func_names = self.get_source_func_names()
        if not all_source_func_names:
            return [], []
        if all_source_func_names == ["main"]:
            return all_source_func_names, []
        n_total = len(all_source_func_names)
        name_to_index_total = {name: i for i, name in enumerate(all_source_func_names)}

        # Step 1: Build the adjacency matrix for ALL functions
        # adj_matrix_total[i, j] = 1 means function i calls function j
        adj_matrix_total = np.zeros((n_total, n_total), dtype=int)
        for i, func_name in enumerate(all_source_func_names):
            # Ensure func_name is a key in self.func_callls (or func_calls)
            # and that self.func_callls[func_name] is iterable
            if func_name in self.func_callls and self.func_callls[func_name]:
                for called_func_name in self.func_callls[func_name]:
                    if called_func_name in name_to_index_total:
                        j = name_to_index_total[called_func_name]
                        adj_matrix_total[i, j] = 1

        # Step 2: Calculate in-degrees and out-degrees for ALL functions
        in_degrees_total = np.sum(adj_matrix_total, axis=0)  # Sum of each column (how many call this function)
        out_degrees_total = np.sum(adj_matrix_total, axis=1) # Sum of each row (how many this function calls)

        # Step 3: Identify and filter out isolated functions
        # These are functions to be included in the topological sort
        eligible_original_indices = []
        for i in range(n_total):
            is_isolated = (in_degrees_total[i] == 0 and out_degrees_total[i] == 0)
            if not is_isolated:
                eligible_original_indices.append(i)
            # else:
            #     print(f"Debug: Excluding isolated function: {all_source_func_names[i]}")


        if not eligible_original_indices:
            return [], [] # All functions were isolated or no functions to begin with

        # Step 4: Create a new context (names, matrix) for ELIGIBLE functions only
        eligible_func_names = [all_source_func_names[i] for i in eligible_original_indices]
        n_eligible = len(eligible_func_names)
        
        # Sub-matrix for eligible functions
        adj_matrix_eligible = adj_matrix_total[np.ix_(eligible_original_indices, eligible_original_indices)]

        # Step 5: Perform Topological Sort (Kahn's Algorithm) on the eligible functions
        # In-degrees for the subgraph of eligible functions
        in_degrees_eligible = np.sum(adj_matrix_eligible, axis=0)
        
        # Queue stores indices RELATIVE to the eligible_func_names list / adj_matrix_eligible
        queue = [i for i, deg in enumerate(in_degrees_eligible) if deg == 0]
        
        ordered_funcs_result = []
        processed_nodes_count = 0

        while queue:
            # u_idx is an index within the 'eligible_func_names' list
            u_idx_eligible = queue.pop(0) 
            ordered_funcs_result.append(eligible_func_names[u_idx_eligible])
            processed_nodes_count += 1

            # For each function v_idx_eligible that u_idx_eligible calls:
            for v_idx_eligible in range(n_eligible):
                if adj_matrix_eligible[u_idx_eligible, v_idx_eligible] == 1:
                    in_degrees_eligible[v_idx_eligible] -= 1
                    if in_degrees_eligible[v_idx_eligible] == 0:
                        queue.append(v_idx_eligible)
        
        # Step 6: Handle cycles (if any) among eligible functions
        if processed_nodes_count != n_eligible:
            remaining_eligible_in_cycle = [
                name for name in eligible_func_names if name not in ordered_funcs_result
            ]
            ordered_funcs_result.extend(remaining_eligible_in_cycle)

        never_called_funcs = [i for i in all_source_func_names if i not in ordered_funcs_result]
        
        return ordered_funcs_result, never_called_funcs
    
    def remove_funcs(self, funcs:list[str]):
        temp:str = self.text
        for func_id in funcs:
            func_body = self.functions[func_id]["func_body"]
            temp = temp.replace(func_body, "")
        return temp
    
    def get_source_func_names(self):
        return [i for i in self.functions.keys()]
    
    def get_structs(self):
        query = """(struct_specifier
            (field_declaration_list)
        )@1"""
        Q = C_LANGUAGE.query(query)
        return [node for node, capture in Q.captures(self.root_node)]
        # return [node for node in Q.captures(self.root_node)["1"]]
            
