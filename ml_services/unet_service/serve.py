"""U-Net wildfire spread service (FastAPI). Local: python serve.py --port 8081. Vertex AI: started by the Dockerfile."""
import argparse, os
from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse
import inference

app = FastAPI(title='Fight Fire With AI - U-Net service')
HEALTH_ROUTE = os.environ.get('AIP_HEALTH_ROUTE', '/health')
PREDICT_ROUTE = os.environ.get('AIP_PREDICT_ROUTE', '/predict')


def _answer(inst):
    if 'bbox' in inst:                       # backend contract (bbox + date + time_horizon)
        return inference.predict_contract(inst)
    return inference.serve_request(inst)    # older lat/lon requests (Deploy & test examples)


@app.get(HEALTH_ROUTE)
def health():
    models = inference.available_models()
    return {'status': 'ok', 'models_loaded': bool(models.get('hourly')), 'models': models}


@app.post(PREDICT_ROUTE)
def predict(body: dict = Body(...)):
    try:
        if isinstance(body.get('instances'), list):          # Vertex AI wrapper in -> wrapper out
            params = body.get('parameters') or {}
            return {'predictions': [_answer({**params, **inst}) for inst in body['instances']]}
        return _answer(body)                                   # raw request -> bare FeatureCollection
    except inference.ContractError as ex:
        return JSONResponse(status_code=ex.status, content={'error': str(ex)})
    except Exception as ex:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={'error': f'U-Net internal error: {ex}'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the U-Net service')
    parser.add_argument('--port', type=int, default=int(os.environ.get('AIP_HTTP_PORT', 8081)))
    parser.add_argument('--host', default='0.0.0.0')
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port)