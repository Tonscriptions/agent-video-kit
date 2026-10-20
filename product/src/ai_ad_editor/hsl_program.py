"""Compile the existing generated frame expressions to a bounded native DAG.

No eval, executable strings, imports or user-selected operations. This accepts
only the arithmetic vocabulary emitted by the HSL author-clock compiler.
"""
from __future__ import annotations
import ast
import math
import re
import struct
from .errors import AppError

MAGIC=b'AVKHSL01'
MAX_PROGRAM_BYTES=32*1024-512
OPS={ast.Add:2,ast.Sub:3,ast.Mult:4,ast.Div:5}
FUNCTIONS={'clip':(7,3),'lt':(8,2),'pow':(9,2),'exp':(10,1),'log':(11,1),'if_':(12,3)}


def compile_program(expressions):
    if len(expressions)!=25:raise AppError('SELECTIVE_HSL_PROGRAM_INVALID','HSL 程序必须包含 25 个通道',exit_code=6)
    nodes=[];indices={};depths=[]
    def add(op,a=0,b=0,c=0,*,depth=1):
        if depth>128:raise AppError('SELECTIVE_HSL_BUDGET','HSL 程序深度超过 128',exit_code=2)
        raw=struct.pack('<IIII',op,a,b,c)
        if raw not in indices:
            if 112+(len(nodes)+1)*16>MAX_PROGRAM_BYTES:
                raise AppError('SELECTIVE_HSL_BUDGET','HSL 原生程序超过有界配额',exit_code=2)
            indices[raw]=len(nodes);nodes.append(raw);depths.append(depth)
        return indices[raw]
    def visit(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float) and math.isfinite(node.value):
            a,b=struct.unpack('<II',struct.pack('<d',float(node.value)));return add(0,a,b)
        if isinstance(node,ast.Name) and node.id in ('t','T'):return add(1)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.USub,ast.UAdd)):
            a=visit(node.operand);return add(6,a,depth=depths[a]+1) if isinstance(node.op,ast.USub) else a
        if isinstance(node,ast.BinOp) and type(node.op) in OPS:
            a,b=visit(node.left),visit(node.right);return add(OPS[type(node.op)],a,b,depth=max(depths[a],depths[b])+1)
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in FUNCTIONS and not node.keywords:
            op,count=FUNCTIONS[node.func.id]
            if len(node.args)==count:
                args=[visit(n) for n in node.args];return add(op,*args,depth=max(depths[a] for a in args)+1)
        raise AppError('SELECTIVE_HSL_PROGRAM_INVALID','HSL 作者表达式包含未支持的结构',exit_code=6)
    roots=[]
    for expression in expressions:
        if not isinstance(expression,str) or len(expression)>64*1024:
            raise AppError('SELECTIVE_HSL_BUDGET','HSL 作者表达式超出预算',exit_code=2)
        try:tree=ast.parse(re.sub(r'\bif\(', 'if_(', expression),mode='eval')
        except (SyntaxError,RecursionError,MemoryError) as exc:
            raise AppError('SELECTIVE_HSL_PROGRAM_INVALID','无法编译 HSL 作者表达式',exit_code=6) from exc
        roots.append(visit(tree.body))
    payload=MAGIC+struct.pack('<I25I',len(nodes),*roots)+b''.join(nodes)
    return payload,{'format':MAGIC.decode(),'bytes':len(payload),'nodes':len(nodes),'max_depth':max(depths)}
