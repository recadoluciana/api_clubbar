#!/bin/bash
cd /home/crispim/projetos/bitbeer/api_bitbeer
source venv_api/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
