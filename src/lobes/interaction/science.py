from ..base import BaseAbility
import logging
import subprocess
import asyncio
from src.tools.error_tracker import error_tracker

logger = logging.getLogger("Lobe.Interaction.Science")

class ScienceAbility(BaseAbility):
    """
    Empirical Verification via Code Execution (The Mini Lab).
    """
    async def execute(self, instruction: str) -> str:
        """
        The Mini Lab (Science Lobe).
        Executes Pure Computation via SymPy, NumPy, and SciPy.
        Safety: No subprocess, no exec, no network, no I/O.
        """
        logger.info(f"ScienceAbility executing: {instruction[:50]}...")
        
        # AI-DRIVEN: Let LLM classify if this is computational vs conceptual
        # Architecture Compliance: "No Heuristics" - AI decides routing
        is_computational = await self._is_computational(instruction)
        
        if not is_computational:
            return (f"Science Lobe Error: Received conceptual question instead of computational task. "
                   f"The Science Lobe is designed for pure math/physics calculations (e.g., 'solve: x**2 - 4', 'eval: sqrt(25)'). "
                   f"For theoretical discussions, use a different lobe or research tool.")
        
        try:
            # 1. PARSE INTENT
            # Basic routing based on prefix.
            # "solve: x**2 - 4"
            # "stats: 1, 2, 3, 4"
            # "eval: sqrt(25)"
            
            if ":" in instruction:
                mode, payload = instruction.split(":", 1)
                mode = mode.strip().lower()
                payload = payload.strip()
                
                # If "mode" looks like Python code (has parens, operators), treat as eval
                if "(" in mode or "+" in mode or "-" in mode or "*" in mode or "=" in mode:
                    mode = "eval"
                    payload = instruction.strip()
            else:
                # Default to eval if no prefix
                mode = "eval"
                payload = instruction.strip()
            
            # Detect non-math Python code and give helpful error
            if "print(" in payload.lower() or "str(" in payload.lower():
                return "Science Lobe only supports math expressions (e.g., 'eval: 2+2', 'solve: x**2-4'). For Python code, use a different approach."
            
            # 2. EXECUTE BY DOMAIN
            if mode == "eval":
                return self._run_math_evaluate(payload)
            elif mode == "solve":
                return self._run_math_solve(payload)
            elif mode == "stats":
                return self._run_stats(payload)
            elif mode == "physics":
                return self._run_physics(payload)
            elif mode == "chemistry":
                return self._run_chemistry(payload)
            elif mode == "matrix":
                return self._run_matrix(payload)
            elif mode == "experiment":
                return await self._design_experiment(payload)
            else:
                # Unknown mode - try to eval the whole thing as fallback
                return self._run_math_evaluate(instruction.strip())

        except Exception as e:
            logger.error(f"Science Execution Failed: {e}")
            error_tracker.log_lobe_failure(
                lobe_name="ScienceLobe",
                error=e,
                instruction=instruction
            )
            return f"Science Error: {str(e)}"

    def _run_math_evaluate(self, code: str) -> str:
        """Symbolic Math Evaluation (SymPy)"""
        import sympy
        from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
        
        transformations = (standard_transformations + (implicit_multiplication_application,))
        
        # Limit scope to sympy functions
        context = {name: getattr(sympy, name) for name in dir(sympy) if not name.startswith("_")}
        context.update({"abs": abs, "min": min, "max": max, "round": round})
        
        try:
            expr = parse_expr(code, local_dict=context, transformations=transformations, evaluate=True)
            # Evaluate to float if possible for clarity, else return symbolic
            result = expr.evalf(4) if expr.is_number else expr
            return f"Math Result: {str(result)}"
        except Exception as e:
            return f"Math syntax error: {str(e)}"

    def _run_math_solve(self, equation_str: str) -> str:
        """Solve Algebraic Equations (SymPy)"""
        import sympy
        from sympy import symbols, solve, Eq
        from sympy.parsing.sympy_parser import parse_expr
        
        # Heuristic: "x**2 - 4" or "x**2 = 4"
        try:
            if "=" in equation_str:
                lhs_str, rhs_str = equation_str.split("=")
                lhs = parse_expr(lhs_str)
                rhs = parse_expr(rhs_str)
                eq = Eq(lhs, rhs)
            else:
                # Assume = 0
                eq = parse_expr(equation_str)
            
            # Identify symbols
            free_symbols = eq.free_symbols
            result = solve(eq, free_symbols)
            return f"Solution: {str(result)}"
        except Exception as e:
            return f"Solver error: {str(e)}"

    def _run_stats(self, data_str: str) -> str:
        """Statistical Analysis (NumPy/SciPy)"""
        import numpy as np
        import scipy.stats as stats
        import ast
        
        try:
            # Safe parse of list: "1, 2, 3" -> [1, 2, 3]
            if not data_str.startswith("["):
                data_str = f"[{data_str}]"
            data = ast.literal_eval(data_str)
            
            if not isinstance(data, list):
                return "Error: Stats input must be a list of numbers."
            
            arr = np.array(data)
            
            res = {
                "mean": float(np.mean(arr)),
                "median": float(np.median(arr)),
                "stdev": float(np.std(arr)),
                "variance": float(np.var(arr)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr))
            }
            
            # Simple report
            return f"Statistics Report:\n" + "\n".join([f"- {k}: {v:.4f}" for k, v in res.items()])
            
        except Exception as e:
            return f"Stats error: {str(e)}"

    def _load_db(self):
        """Lazy Load Science DB"""
        import json
        if hasattr(self, "_db") and self._db:
            return self._db
            
        try:
            with open("src/data/science_db.json", "r") as f:
                self._db = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load science_db.json: {e}")
            self._db = {"elements": {}, "constants": {}}
        return self._db

    def _run_physics(self, query: str) -> str:
        """Physical Constants & Units"""
        db = self._load_db()
        constants = db.get("constants", {})
        
        # Fallback Scipy lookup
        import scipy.constants as const
        
        query = query.strip()
        
        # Case-insensitive lookup: try original, lowercase, uppercase
        matched_key = None
        for key in constants:
            if key.lower() == query.lower():
                matched_key = key
                break
        
        if matched_key:
            c = constants[matched_key]
            return f"Constant '{matched_key}' ({c['name']}): {c['value']} {c['unit']}"
        elif hasattr(const, query) or hasattr(const, query.lower()):
            val = getattr(const, query, None) or getattr(const, query.lower(), None)
            return f"Constant '{query}' (SciPy): {val}"
        else:
            avail = ", ".join(list(constants.keys())[:5])
            return f"Constant '{query}' not found. Available: {avail}..."

    def _run_chemistry(self, query: str) -> str:
        """Periodic Table Lookup (Full DB)"""
        db = self._load_db()
        elements = db.get("elements", {})
        
        query = query.strip()
        
        # Case-insensitive lookup for element symbol
        matched_key = None
        for key in elements:
            if key.lower() == query.lower():
                matched_key = key
                break
        
        found = None
        if matched_key:
            found = elements[matched_key]
            q = matched_key
        else:
            # Search by name (case-insensitive)
            for k, v in elements.items():
                if v["name"].lower() == query.lower():
                    found = v
                    q = k
                    break
        
        if found:
            return f"Element: {found['name']} (Symbol: {q})\nAtomic Number: {found['atomic_number']}\nAtomic Mass: {found['mass']}\nCategory: {found.get('category', 'Unknown')}"
        else:
            return "Element not found in database. Try using Symbol (e.g., U, Og) or Name (Uranium)."

    def _run_matrix(self, matrix_str: str) -> str:
        """Matrix Operations (NumPy)"""
        import numpy as np
        import ast
        
        try:
            # Parse "[[1,2],[3,4]] | det" or just "[[1,2],[3,4]]"
            if "|" in matrix_str:
                data_part, op = matrix_str.split("|")
                op = op.strip().lower()
            else:
                data_part = matrix_str
                op = "info"
                
            data = ast.literal_eval(data_part.strip())
            arr = np.array(data)
            
            if op == "det":
                res = np.linalg.det(arr)
                return f"Determinant: {res:.4f}"
            elif op == "eig":
                vals, vecs = np.linalg.eig(arr)
                return f"Eigenvalues: {vals}\nEigenvectors:\n{vecs}"
            elif op == "inv":
                inv = np.linalg.inv(arr)
                return f"Inverse:\n{inv}"
            elif op == "info":
                return f"Shape: {arr.shape}\nRank: {np.linalg.matrix_rank(arr)}"
            else:
                return f"Unknown matrix op '{op}'. Try: det, eig, inv."
                
        except Exception as e:
            return f"Matrix Error: {str(e)}"

    async def _design_experiment(self, question: str) -> str:
        """Neuro-Symbolic Experimental Design"""
        try:
            with open("src/prompts/science_experiment.txt", "r") as f:
                template = f.read()
                
            prompt = template.format(question=question)
            engine = self.bot.engine_manager.get_active_engine()
            design = await self.bot.loop.run_in_executor(None, engine.generate_response, prompt)
            
            return f"### [EXPERIMENTAL DESIGN]\n{design}"
        except Exception as e:
            return f"Design Error: {str(e)}"

    async def _is_computational(self, instruction: str) -> bool:
        """
        AI-driven classification: Is this a computational task?
        
        Architecture Compliance: Uses LLM instead of keyword matching.
        Falls back to symbol/prefix detection if AI unavailable.
        """
        # FAST PATH: Known science prefixes are always computational
        science_prefixes = ["solve:", "eval:", "stats:", "matrix:", "physics:", "chemistry:", "experiment:"]
        if any(instruction.lower().strip().startswith(p) for p in science_prefixes):
            return True
        
        # FAST PATH: Clear math symbols indicate computational
        math_symbols = ["=", "+", "*", "/", "^", "[", "(", ")", "sqrt", "sin", "cos", "log", "∫", "∑", "**", "-"]
        if any(sym in instruction for sym in math_symbols):
            return True
        
        # AI PATH: For ambiguous cases, ask LLM to classify
        try:
            engine = self.bot.engine_manager.get_active_engine()
            if not engine:
                return False  # No engine, no AI classification possible
            
            prompt = f"""Classify this input for the Science Lobe.

INPUT: {instruction}

Is this a COMPUTATIONAL task (math, physics formulas, statistics, symbolic equations)?
Or is this a CONCEPTUAL question (explanations, theory, discussions)?

RESPOND WITH ONLY ONE WORD: COMPUTATIONAL or CONCEPTUAL"""

            response = await self.bot.loop.run_in_executor(
                None, 
                lambda: engine.generate_response(prompt)
            )
            
            return "COMPUTATIONAL" in response.strip().upper()
            
        except Exception as e:
            logger.warning(f"AI classification failed: {e}")
            return False  # Conservative: reject if unsure

