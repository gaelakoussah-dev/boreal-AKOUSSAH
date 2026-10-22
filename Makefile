PY ?= python

tout:
	$(PY) lancer.py

rejeu:
	$(PY) test_rejeu.py

dashboard:
	streamlit run dashboard.py

surveiller:
	$(PY) surveiller.py

.PHONY: tout rejeu dashboard surveiller
