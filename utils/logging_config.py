#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 31 23:17:08 2025

@author: fran
"""

import logging
from logging.handlers import RotatingFileHandler


_LOGGER = None




def configure_logging(log_file: str = "marktanteil.log"):
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER


    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    
    formatter = logging.Formatter(fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    
    
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    
    fh = RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=3)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    
    _LOGGER = logger
    return logger
    
    
    
    
def get_logger(name: str):
    return logging.getLogger(name)