from __future__ import annotations
import ast

class PolicyRegistry:
    """Static policy gate. This is not a hostile-code sandbox; execute untrusted policies in a container."""
    def __init__(self): self._items={}
    def validate_source(self, source:str):
        if len(source) > 16000: raise ValueError('policy source too large')
        tree=ast.parse(source, mode='exec')
        banned_names={'subprocess','socket','requests','urllib','os','sys','pathlib','shutil','ctypes','pickle','marshal','builtins','eval','exec','compile','__import__','open','input','globals','locals','vars','getattr','setattr','delattr','breakpoint'}
        allowed_nodes=(ast.Module,ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef,ast.arguments,ast.arg,ast.Return,ast.Pass,ast.Assign,ast.AnnAssign,ast.AugAssign,ast.Name,ast.Load,ast.Store,ast.Constant,ast.Expr,ast.If,ast.For,ast.While,ast.Break,ast.Continue,ast.List,ast.Tuple,ast.Set,ast.Dict,ast.Subscript,ast.Slice,ast.BinOp,ast.UnaryOp,ast.BoolOp,ast.Compare,ast.Attribute,ast.Call,ast.keyword,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.FloorDiv,ast.Mod,ast.Pow,ast.USub,ast.UAdd,ast.Not,ast.And,ast.Or,ast.Eq,ast.NotEq,ast.Lt,ast.LtE,ast.Gt,ast.GtE,ast.In,ast.NotIn,ast.Is,ast.IsNot,ast.ListComp,ast.SetComp,ast.DictComp,ast.comprehension,ast.IfExp)
        for n in ast.walk(tree):
            if not isinstance(n, allowed_nodes): raise ValueError(f'disallowed AST node: {type(n).__name__}')
            if isinstance(n,(ast.Import,ast.ImportFrom)): raise ValueError('imports are disabled')
            if isinstance(n,ast.Name) and (n.id in banned_names or n.id.startswith('__')): raise ValueError(f'banned name: {n.id}')
            if isinstance(n,ast.Attribute) and (n.attr.startswith('__') or n.attr in banned_names): raise ValueError(f'banned attribute: {n.attr}')
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in banned_names: raise ValueError(f'banned call: {n.func.id}')
        names={n.name for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))}
        if not names: raise ValueError('policy source defines no class/function')
        return True
    def add(self,name,policy): self._items[name]=policy
    def get(self,name): return self._items[name]
