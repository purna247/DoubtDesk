"""Import every ORM model so SQLAlchemy can resolve cross-module relationships.

The API loads models through its routers, while the background worker does not.
Importing this module gives both processes the same configured model registry.
"""

from app.modules.academics import models as academics_models  # noqa: F401
from app.modules.analytics import models as analytics_models  # noqa: F401
from app.modules.assessments import models as assessments_models  # noqa: F401
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.doubts import models as doubts_models  # noqa: F401
from app.modules.institutions import models as institution_models  # noqa: F401
from app.modules.interventions import models as intervention_models  # noqa: F401
from app.modules.jobs import models as jobs_models  # noqa: F401
from app.modules.knowledge import models as knowledge_models  # noqa: F401
from app.modules.learning import models as learning_models  # noqa: F401
from app.modules.notifications import models as notification_models  # noqa: F401
from app.modules.questions import models as question_models  # noqa: F401
from app.modules.sources import models as source_models  # noqa: F401
from app.modules.sources import academic_models as academic_models  # noqa: F401
