# PROYECTO 1: Simulador de Gestor de BD (BD2)

## 🚀 Estado Actual: Análisis Léxico (Scanner)
Se ha implementado el componente base del parser SQL:
- **Funcionalidad**: Tokenización completa de sentencias SQL (CREATE, SELECT, INSERT, DELETE).
- **Soporte Especial**: Reconocimiento de números negativos y decimales para soporte de coordenadas en R-Tree.
- **Automatización**: Procesamiento por lotes de archivos `.txt` desde el directorio `/input` con salida de tokens en el mismo directorio (`*_tokens.txt`).
- **Formato de Salida**: Exportación compatible con la especificación `TOKEN(TYPE, "TEXT")`.

**Ejecución:**
```bash
PYTHONPATH=parser python3 parser/main.py
```

