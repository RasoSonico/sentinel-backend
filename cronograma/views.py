from rest_framework import viewsets, status, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Prefetch, Count, Sum, F, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend

from .models import Schedule, Activity, ActivityConcept, CriticalPath, CriticalPathActivity
from .serializers import (
    ScheduleListSerializer, ScheduleDetailSerializer, ActivitySerializer,
    ActivityConceptSerializer, CriticalPathSerializer, CriticalPathActivitySerializer
)
from obra.models import Construction
from catalogo.models import Concept
from .filters import ScheduleFilter, ActivityFilter


class ScheduleViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar cronogramas de obra"""
    queryset = Schedule.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = ScheduleFilter
    search_fields = ['name', 'description', 'construction__name']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ScheduleListSerializer
        return ScheduleDetailSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = Schedule.objects.all()
        
        # Filtrar por obras asignadas al usuario
        if user.is_authenticated and not user.is_staff:
            from obra.models import UserConstruction
            user_constructions = UserConstruction.objects.filter(
                user=user,
                is_active=True
            ).values_list('construction', flat=True)
            queryset = queryset.filter(construction__in=user_constructions)
        
        # Filtrar por obra si se proporciona el ID
        construction_id = self.request.query_params.get('construction_id')
        if construction_id:
            queryset = queryset.filter(construction_id=construction_id)
        
        # Filtrar por estado activo/inactivo
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            is_active = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active)
        
        # Precargar relaciones para optimizar consultas
        queryset = queryset.select_related('construction')
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Endpoint para desactivar un cronograma"""
        schedule = self.get_object()
        schedule.deactivate()
        return Response({"message": "Cronograma desactivado correctamente"})
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Endpoint para duplicar un cronograma existente"""
        original_schedule = self.get_object()
        
        # Crear nuevo cronograma
        new_schedule = Schedule.objects.create(
            construction=original_schedule.construction,
            name=f"Copia de {original_schedule.name}",
            description=original_schedule.description,
            is_active=True
        )
        
        # Duplicar actividades y sus conceptos asociados
        for activity in original_schedule.activities.all():
            new_activity = Activity.objects.create(
                schedule=new_schedule,
                name=activity.name,
                description=activity.description,
                start_date=activity.start_date,
                end_date=activity.end_date,
                progress_percentage=0.0  # Reiniciar progreso
            )
            
            # Duplicar asociaciones con conceptos
            for ac in activity.activity_concepts.all():
                ActivityConcept.objects.create(
                    activity=new_activity,
                    concept=ac.concept
                )
        
        serializer = self.get_serializer(new_schedule)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def validate(self, request, pk=None):
        """Endpoint para validar un cronograma"""
        schedule = self.get_object()
        
        try:
            # Ejecutar validaciones
            schedule.validate_construction_budget()
            schedule.validate_dates()
            
            # Verificar conceptos sin incluir
            all_concepts = set(Concept.objects.filter(
                work_item__catalog__construction=schedule.construction
            ).values_list('id', flat=True))
            
            used_concepts = set(ActivityConcept.objects.filter(
                activity__schedule=schedule
            ).values_list('concept_id', flat=True))
            
            missing_concepts = all_concepts - used_concepts
            
            return Response({
                "is_valid": True if not missing_concepts else False,
                "missing_concepts_count": len(missing_concepts),
                "missing_concepts": list(missing_concepts) if missing_concepts else []
            })
            
        except Exception as e:
            return Response({
                "is_valid": False,
                "errors": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class ActivityViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar actividades de un cronograma"""
    queryset = Activity.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ActivitySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = ActivityFilter
    search_fields = ['name', 'description']
    
    def get_queryset(self):
        user = self.request.user
        queryset = Activity.objects.all()
        
        # Filtrar por obras asignadas al usuario (a través de schedule)
        if user.is_authenticated and not user.is_staff:
            from obra.models import UserConstruction
            user_constructions = UserConstruction.objects.filter(
                user=user,
                is_active=True
            ).values_list('construction', flat=True)
            queryset = queryset.filter(schedule__construction__in=user_constructions)
        
        # Filtrar por cronograma si se proporciona el ID
        schedule_id = self.request.query_params.get('schedule_id')
        if schedule_id:
            queryset = queryset.filter(schedule_id=schedule_id)
        
        # Precargar relaciones para optimizar consultas
        queryset = queryset.select_related('schedule')
        queryset = queryset.prefetch_related(
            Prefetch('activity_concepts', queryset=ActivityConcept.objects.select_related('concept'))
        )
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def add_concepts(self, request, pk=None):
        """Endpoint para añadir conceptos a una actividad existente"""
        activity = self.get_object()
        concept_ids = request.data.get('concept_ids', [])
        
        added_concepts = []
        existing_concepts = []
        
        for concept_id in concept_ids:
            try:
                concept = Concept.objects.get(id=concept_id)
                _, created = ActivityConcept.objects.get_or_create(
                    activity=activity,
                    concept=concept
                )
                
                if created:
                    added_concepts.append(concept_id)
                else:
                    existing_concepts.append(concept_id)
                    
            except Concept.DoesNotExist:
                pass
        
        return Response({
            "added_concepts": added_concepts,
            "existing_concepts": existing_concepts
        })
    
    @action(detail=True, methods=['post'])
    def remove_concepts(self, request, pk=None):
        """Endpoint para eliminar conceptos de una actividad"""
        activity = self.get_object()
        concept_ids = request.data.get('concept_ids', [])
        
        deleted_count = ActivityConcept.objects.filter(
            activity=activity,
            concept_id__in=concept_ids
        ).delete()[0]
        
        return Response({
            "deleted_count": deleted_count
        })
    
    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """Endpoint para actualizar el porcentaje de avance de una actividad"""
        activity = self.get_object()
        progress = request.data.get('progress_percentage')
        
        if progress is None:
            return Response({"error": "Se requiere el campo progress_percentage"}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        try:
            progress = float(progress)
            if progress < 0 or progress > 100:
                return Response({"error": "El porcentaje debe estar entre 0 y 100"}, 
                                status=status.HTTP_400_BAD_REQUEST)
            
            activity.progress_percentage = progress
            activity.save()
            
            serializer = self.get_serializer(activity)
            return Response(serializer.data)
            
        except ValueError:
            return Response({"error": "El valor debe ser numérico"}, 
                            status=status.HTTP_400_BAD_REQUEST)


class CriticalPathViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar rutas críticas"""
    queryset = CriticalPath.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CriticalPathSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = CriticalPath.objects.all()
        
        # Filtrar por obras asignadas al usuario (a través de schedule)
        if user.is_authenticated and not user.is_staff:
            from obra.models import UserConstruction
            user_constructions = UserConstruction.objects.filter(
                user=user,
                is_active=True
            ).values_list('construction', flat=True)
            queryset = queryset.filter(schedule__construction__in=user_constructions)
        
        # Filtrar por cronograma si se proporciona el ID
        schedule_id = self.request.query_params.get('schedule_id')
        if schedule_id:
            queryset = queryset.filter(schedule_id=schedule_id)
        
        # Precargar relaciones para optimizar consultas
        queryset = queryset.select_related('schedule')
        queryset = queryset.prefetch_related(
            Prefetch('critical_activities', queryset=CriticalPathActivity.objects.select_related('activity'))
        )
        
        return queryset
    
    @action(detail=False, methods=['post'])
    def calculate(self, request):
        """
        Endpoint para calcular la ruta crítica de un cronograma
        Este es un cálculo simplificado, en un caso real podría implementarse
        un algoritmo más complejo como CPM (Critical Path Method)
        """
        schedule_id = request.data.get('schedule_id')
        if not schedule_id:
            return Response({"error": "Se requiere el ID del cronograma"}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        try:
            schedule = Schedule.objects.get(id=schedule_id)
            activities = schedule.activities.all().order_by('start_date')
            
            if not activities:
                return Response({"error": "El cronograma no tiene actividades"}, 
                                status=status.HTTP_400_BAD_REQUEST)
            
            # Crear o actualizar la ruta crítica
            critical_path, created = CriticalPath.objects.update_or_create(
                schedule=schedule,
                defaults={
                    'calculated_at': timezone.now(),
                    'notes': "Ruta crítica calculada automáticamente"
                }
            )
            
            # Eliminar actividades críticas anteriores si existían
            critical_path.critical_activities.all().delete()
            
            # Versión simplificada: seleccionar actividades consecutivas sin holgura
            # En un cálculo real se usaría forward pass y backward pass para determinar
            # las actividades críticas basadas en early/late start y finish
            
            # Para este MVP, simplemente tomamos las actividades más largas
            # que no tienen solapamiento entre ellas
            selected_activities = []
            current_end = None
            
            for idx, activity in enumerate(activities):
                if idx == 0 or activity.start_date >= current_end:
                    selected_activities.append(activity)
                    current_end = activity.end_date
            
            # Guardar las actividades críticas
            for idx, activity in enumerate(selected_activities):
                CriticalPathActivity.objects.create(
                    critical_path=critical_path,
                    activity=activity,
                    sequence_order=idx + 1
                )
            
            serializer = self.get_serializer(critical_path)
            return Response(serializer.data)
            
        except Schedule.DoesNotExist:
            return Response({"error": "Cronograma no encontrado"}, 
                            status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, 
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)