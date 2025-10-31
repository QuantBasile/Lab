## 📁 Estructura de proyecto

```
marktanteil_lab/
├─ README.md
├─ main.py
├─ app/
│  ├─ __init__.py
│  └─ app.py                 # Crea la raíz Tk y lanza la MainWindow
├─ ui/
│  ├─ __init__.py
│  ├─ main_window.py         # Ventana principal (controles + tabla)
│  └─ table_widget.py        # TableFrame: envoltorio ttk.Treeview + scroll para DataFrame
├─ data/
│  ├─ __init__.py
│  └─ fake_generator.py      # Generador vectorizado de datos fake (3 meses)
├─ services/
│  ├─ __init__.py
│  └─ data_service.py        # Orquesta la generación/carga y entrega DataFrames a la UI
└─ utils/
   ├─ __init__.py
   └─ logging_config.py      # Logging uniforme (rotating file handler)
```
