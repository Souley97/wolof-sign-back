class OptionsMiddleware:
    """
    Middleware to handle OPTIONS requests properly for CORS preflight.
    This prevents redirects on OPTIONS requests which cause CORS errors.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Handle OPTIONS requests
        if request.method == "OPTIONS":
            response = self.get_response(request)
            if response.status_code == 301 or response.status_code == 302:
                # Don't redirect OPTIONS requests
                response.status_code = 200
                response["Allow"] = "GET, POST, PUT, DELETE, OPTIONS"
                response["Access-Control-Allow-Origin"] = "*"
                response["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-CSRFToken"
                response["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
                return response
            return response
        else:
            # Process regular requests
            return self.get_response(request)

class MediaFilesMiddleware:
    """
    Middleware pour gérer correctement les en-têtes CORS pour les fichiers média
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Si la requête concerne un fichier média
        if request.path.startswith('/media/'):
            # Ajouter les en-têtes CORS pour les fichiers média
            response["Access-Control-Allow-Origin"] = "*"
            response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            response["Access-Control-Allow-Headers"] = "Origin, Content-Type, Accept"
            
            # Ajouter des en-têtes de cache pour améliorer les performances
            response["Cache-Control"] = "public, max-age=86400"  # Cache pour 24 heures
            
            # Configurer le type de contenu correct pour les PDF
            if request.path.endswith('.pdf'):
                response["Content-Type"] = "application/pdf"
                response["Content-Disposition"] = "inline"
        
        return response 