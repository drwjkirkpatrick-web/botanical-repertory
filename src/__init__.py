"""
Botanical Medicine Repertory

A local, vector-searchable botanical medicine database for clinical use.
"""

__version__ = "1.0.0"
__author__ = "Walker (Hermes Agent)"

from .models import Botanical, Indication, BotanicalIndicationLink, SafetyProfile
from .database import BotanicalDatabase
from .repertory import BotanicalRepertory

__all__ = [
    "Botanical",
    "Indication", 
    "BotanicalIndicationLink",
    "SafetyProfile",
    "BotanicalDatabase",
    "BotanicalRepertory",
]