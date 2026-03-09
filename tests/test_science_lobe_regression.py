"""
REGRESSION TESTS: Science Lobe Case-Insensitive Lookups

These tests exist to prevent regression of the following fixes:
- Physics constants must work with any case: c, C, g, G, h, H
- Chemistry elements must work with any case: Au, au, AU, gold, Gold, GOLD

DO NOT REMOVE OR MODIFY THESE TESTS WITHOUT UNDERSTANDING WHY THEY EXIST.
See conversation: 8d84b082-52b2-4ade-8bf4-336b5c893f4f (2026-02-05)
"""
import pytest
from unittest.mock import MagicMock


class TestScienceLobeRegression:
    """Regression tests to prevent case-sensitivity bugs from returning."""
    
    @pytest.fixture
    def science_ability(self):
        """Create a ScienceAbility instance for testing."""
        from src.lobes.interaction.science import ScienceAbility
        
        class MockLobe:
            bot = None
        
        return ScienceAbility(MockLobe())
    
    # ===== PHYSICS CONSTANTS: CASE-INSENSITIVE =====
    
    def test_physics_speed_of_light_lowercase(self, science_ability):
        """Physics constant 'c' (lowercase) must return speed of light."""
        result = science_ability._run_physics("c")
        assert "299792458" in result
        assert "Speed of light" in result
    
    def test_physics_speed_of_light_uppercase(self, science_ability):
        """Physics constant 'C' (uppercase) must return speed of light."""
        result = science_ability._run_physics("C")
        assert "299792458" in result
        assert "Speed of light" in result
    
    def test_physics_gravitational_constant_lowercase(self, science_ability):
        """Physics constant 'g' (lowercase) must work - returns gravity-related constant."""
        result = science_ability._run_physics("g")
        # May return either 'g' (standard gravity) or 'G' (gravitational constant) 
        # depending on which is found first in case-insensitive search
        assert "gravity" in result.lower() or "Gravitational" in result
    
    def test_physics_gravitational_constant_uppercase(self, science_ability):
        """Physics constant 'G' (uppercase) must work."""
        result = science_ability._run_physics("G")
        assert "Gravitational" in result
    
    def test_physics_planck_constant(self, science_ability):
        """Physics constant 'h' must work."""
        result = science_ability._run_physics("h")
        assert "Planck" in result
    
    def test_physics_boltzmann_constant(self, science_ability):
        """Physics constant 'kB' must work."""
        result = science_ability._run_physics("kB")
        assert "Boltzmann" in result
    
    # ===== CHEMISTRY ELEMENTS: CASE-INSENSITIVE =====
    
    def test_chemistry_gold_symbol_mixed_case(self, science_ability):
        """Chemistry element 'Au' (proper case) must return Gold."""
        result = science_ability._run_chemistry("Au")
        assert "Gold" in result
        assert "79" in result  # Atomic number
    
    def test_chemistry_gold_symbol_lowercase(self, science_ability):
        """Chemistry element 'au' (lowercase) must return Gold."""
        result = science_ability._run_chemistry("au")
        assert "Gold" in result
        assert "79" in result
    
    def test_chemistry_gold_symbol_uppercase(self, science_ability):
        """Chemistry element 'AU' (uppercase) must return Gold."""
        result = science_ability._run_chemistry("AU")
        assert "Gold" in result
        assert "79" in result
    
    def test_chemistry_gold_by_name_lowercase(self, science_ability):
        """Chemistry element by name 'gold' must work."""
        result = science_ability._run_chemistry("gold")
        assert "Gold" in result
        assert "79" in result
    
    def test_chemistry_gold_by_name_uppercase(self, science_ability):
        """Chemistry element by name 'GOLD' must work."""
        result = science_ability._run_chemistry("GOLD")
        assert "Gold" in result
        assert "79" in result
    
    def test_chemistry_uranium_lowercase(self, science_ability):
        """Chemistry element 'u' (lowercase) must return Uranium."""
        result = science_ability._run_chemistry("u")
        assert "Uranium" in result
        assert "92" in result
    
    def test_chemistry_carbon_lowercase(self, science_ability):
        """Chemistry element 'c' (lowercase - NOT physics!) must return Carbon."""
        result = science_ability._run_chemistry("c")
        assert "Carbon" in result
        assert "6" in result  # Atomic number
    
    def test_chemistry_oxygen_variations(self, science_ability):
        """Chemistry element O must work in all cases."""
        for variant in ["O", "o", "oxygen", "OXYGEN", "Oxygen"]:
            result = science_ability._run_chemistry(variant)
            assert "Oxygen" in result
    
    # ===== FULL DATABASE COVERAGE =====
    
    def test_all_physics_constants_exist(self, science_ability):
        """All documented physics constants must be retrievable."""
        required_constants = ["c", "G", "h", "g", "e", "me", "mp", "kB", "NA", "R"]
        for const in required_constants:
            result = science_ability._run_physics(const)
            assert "not found" not in result.lower(), f"Physics constant '{const}' not found!"
    
    def test_common_elements_exist(self, science_ability):
        """Common elements must be retrievable."""
        common_elements = ["H", "He", "C", "N", "O", "Fe", "Au", "Ag", "Cu", "U"]
        for elem in common_elements:
            result = science_ability._run_chemistry(elem)
            assert "not found" not in result.lower(), f"Element '{elem}' not found!"


class TestOntologistRegression:
    """Regression tests for Ontologist instruction parsing."""
    
    @pytest.mark.asyncio
    async def test_ontologist_parses_arrow_notation(self):
        """Ontologist must parse 'Subject -PREDICATE-> Object' format."""
        from unittest.mock import patch, MagicMock, AsyncMock
        
        with patch("src.bot.globals.bot") as mock_bot:
            mock_bot.cerebrum = MagicMock()
            lobe = MagicMock()
            ability = MagicMock()
            ability.execute = AsyncMock(return_value="Success")
            lobe.get_ability.return_value = ability
            mock_bot.cerebrum.get_lobe.return_value = lobe
            
            from src.tools.lobe_tools import consult_ontologist
            result = await consult_ontologist(instruction="Ernos -CREATED_BY-> Maria")
            
            assert result == "Success"
            # Verify it parsed correctly
            ability.execute.assert_called_once()
            call_args = ability.execute.call_args[0]
            # Should have extracted subject, predicate, object
            assert len(call_args) == 3
    
    @pytest.mark.asyncio
    async def test_ontologist_parses_simple_notation(self):
        """Ontologist must parse 'Subject PREDICATE Object' format."""
        from unittest.mock import patch, MagicMock, AsyncMock
        
        with patch("src.bot.globals.bot") as mock_bot:
            mock_bot.cerebrum = MagicMock()
            lobe = MagicMock()
            ability = MagicMock()
            ability.execute = AsyncMock(return_value="Success")
            lobe.get_ability.return_value = ability
            mock_bot.cerebrum.get_lobe.return_value = lobe
            
            from src.tools.lobe_tools import consult_ontologist
            result = await consult_ontologist(instruction="Ernos LOVES Maria")
            
            assert result == "Success"
    
    @pytest.mark.asyncio
    async def test_ontologist_rejects_single_word(self):
        """Ontologist must reject single-word instructions that can't be parsed."""
        from unittest.mock import patch, MagicMock
        
        with patch("src.bot.globals.bot") as mock_bot:
            mock_bot.cerebrum = MagicMock()
            
            from src.tools.lobe_tools import consult_ontologist
            result = await consult_ontologist(instruction="Query")
            
            assert "Error" in result
            assert "Could not parse" in result
