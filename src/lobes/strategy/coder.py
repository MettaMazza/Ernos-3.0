import logging
import asyncio
import subprocess
import os
import sys
import tempfile
from ..base import BaseAbility  # type: ignore

# Add project root to path for config import
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
try:
    from config import settings  # type: ignore
except ImportError:
    # Only for linter fallback
    settings = None

logger = logging.getLogger("Lobe.Strategy.Coder")

class CoderAbility(BaseAbility):
    """
    The Autonomous Developer.
    Design -> Code -> Test -> Fix Loop.
    """
    
    async def create_script(self, spec: str) -> dict:
        """
        Creates a python script from a spec, verifies it runs, and returns the result.
        Returns: {'success': bool, 'code': str, 'output': str, 'retries': int}
        """
        logger.info(f"Coder initiating session for: {spec}")
        
        # 1. Design Phase
        code = await self._generate_code(spec)
        
        # 2. Test & Fix Loop
        max_retries = 3
        output = ""
        error = ""
        
        for attempt in range(max_retries + 1):
            logger.info(f"Test Run {attempt+1}/{max_retries+1}")
            
            # Write to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
                tmp.write(code)
                tmp_path = tmp.name
                
            try:
                # Execute (Safe Sandbox Wrapper Mock - simplistic for now)
                # In prod, use docker or strict sandbox
                proc = await asyncio.create_subprocess_exec(
                    "python3", tmp_path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                
                output = stdout.decode()
                error = stderr.decode()
                
                if proc.returncode == 0:
                    logger.info("Code execution SUCCESS.")
                    os.unlink(tmp_path)
                    
                    # Audit Report
                    try:
                        await self._report_to_audit(spec, code)
                    except Exception as e:
                        logger.error(f"Failed to send audit report: {e}")
                        
                    return {
                        "success": True, 
                        "code": code, 
                        "output": output,
                        "retries": attempt
                    }
                else:
                    logger.warning(f"Code execution FAILED: {error}")
                    if attempt < max_retries:
                        code = await self._fix_code(code, error)
                    else:
                        os.unlink(tmp_path)
                        return {
                            "success": False,
                            "code": code,
                            "output": error,
                            "retries": attempt
                        }
            except Exception as e:
                logger.error(f"Execution Error: {e}")
                return {"success": False, "error": str(e)}
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    
        return {"success": False, "code": code, "output": "Max retries exceeded"}

    async def _report_to_audit(self, spec: str, code: str):
        if not settings:
            return
            
        choice_id = getattr(settings, "CODE_AUDIT_CHANNEL_ID", None)
        if not choice_id:
            return

        channel = self.bot.get_channel(choice_id)
        if not channel:
            logger.warning(f"Audit channel {choice_id} not found.")
            return

        # Generate summary
        summary = await self._generate_summary(code)
        
        # Build message
        msg_content = f"**🤖 Autonomous Code Generation Report**\n\n**Intent:** {spec}\n\n**Explanation:** {summary}\n"
        
        # Add code block, truncating if necessary to fit Discord 2000 char limit
        # Reserve ~10 chars for formatting
        remaining_budget = 1950 - len(msg_content)
        
        # Ensure budget is an integer and at least 0
        limit: int = int(max(0, remaining_budget))
        
        if len(code) > limit:
            # Explicitly rebuild string to avoid slicing ambiguity
            snippet = str(code)
            # Use explicit slice object to satisfy strict linter
            code_snippet = snippet[slice(0, limit)] + "\n... (truncated)"  # type: ignore
        else:
            code_snippet = code
            
        final_msg = f"{msg_content}\n```python\n{code_snippet}\n```"
        try:
            await channel.send(final_msg)
        except Exception as e:
            logger.error(f"Failed to send message to audit channel: {e}")

    async def _generate_summary(self, code: str) -> str:
        prompt = f"Explain the following Python code in simple, understandable terms for a general audience. Focus on what it *does* and why. Keep it brief (2-3 sentences).\n\nCode:\n{code}"
        engine = self.bot.engine_manager.get_active_engine()
        return await self.bot.loop.run_in_executor(None, engine.generate_response, prompt)

    async def _generate_code(self, spec: str) -> str:
        try:
            with open("src/prompts/coder_design.txt", "r") as f:
                template = f.read()
            prompt = template.format(spec=spec)
            engine = self.bot.engine_manager.get_active_engine()
            return await self.bot.loop.run_in_executor(None, engine.generate_response, prompt)
        except Exception as e:
            return f"print('Generation Error: {e}')"

    async def _fix_code(self, code: str, error: str) -> str:
        try:
            with open("src/prompts/coder_debug.txt", "r") as f:
                template = f.read()
            prompt = template.format(code=code, error=error)
            engine = self.bot.engine_manager.get_active_engine()
            return await self.bot.loop.run_in_executor(None, engine.generate_response, prompt)
        except Exception as e:
            return code # Fallback
