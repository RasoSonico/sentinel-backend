from rest_framework import viewsets, generics, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Case, When, Value, Avg, Q
from django.db.models.functions import Extract
from django.utils import timezone
from rest_framework.views import APIView

from obra.models import Construction
from .models import (Physical, 
                     Estimation, 
                     EstimationDetail, 
                     CommitmentTracking, PhysicalStatusHistory)
from .serializers import (
    PhysicalSerializer, 
    EstimationSerializer, 
    EstimationDetailSerializer, 
    EstimationListSerializer, 
    EstimationDetailedSerializer, 
    CommitmentTrackingSerializer)
from catalogo.models import Concept, Catalog, WorkItem
from django_filters.rest_framework import DjangoFilterBackend
from cronograma.models import Schedule, Activity, ActivityConcept
from datetime import datetime, timedelta

# Vista para crear y listar avances físicos
class PhysicalListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar todos los avances físicos y crear nuevos.
    GET: Lista todos los avances con opción de filtrado
    POST: Crea un nuevo avance
    """
    queryset = Physical.objects.all()
    serializer_class = PhysicalSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['concept', 'status', 'date']
    search_fields = ['comments']
    ordering_fields = ['date', 'volume']
    ordering = ['-date']  # Ordenamiento por defecto: más reciente primero
    
    def get_queryset(self):
        """
        Filtrar avances según las obras asignadas al usuario autenticado
        """
        user = self.request.user
        queryset = super().get_queryset()
        
        # Filtrar por permisos de usuario (solo obras asignadas)
        if user.is_authenticated and not user.is_staff:
            from obra.models import UserConstruction
            
            # Obtener IDs de construcciones asignadas al usuario
            user_constructions = UserConstruction.objects.filter(
                user=user,
                is_active=True
            ).values_list('construction', flat=True)
            
            # Filtrar avances solo de conceptos que pertenecen a obras asignadas
            # Flujo: Physical → Concept → Catalog → Construction
            queryset = queryset.filter(
                concept__catalog__construction__in=user_constructions
            )
        
        # Filtro por rango de fechas
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
            
        # Filtrar por catálogo
        catalog_id = self.request.query_params.get('catalog')
        if catalog_id:
            queryset = queryset.filter(concept__catalog_id=catalog_id)
            
        # Filtrar por partida (work item)
        work_item_id = self.request.query_params.get('work_item')
        if work_item_id:
            queryset = queryset.filter(concept__work_item_id=work_item_id)
            
        return queryset
    
    def perform_create(self, serializer):
        """
        Validar que el usuario tenga acceso a la obra del concepto antes de crear el avance físico
        """
        user = self.request.user
        concept = serializer.validated_data['concept']
        
        # Solo validar si el usuario está autenticado y no es staff
        if user.is_authenticated and not user.is_staff:
            from obra.models import UserConstruction
            
            # Verificar si el usuario tiene acceso a la obra del concepto
            # Flujo de validación: User → UserConstruction → Construction ← Catalog ← Concept
            has_access = UserConstruction.objects.filter(
                user=user,
                construction=concept.catalog.construction,
                is_active=True
            ).exists()
            
            if not has_access:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied(
                    f"No tienes permisos para registrar avances en la obra: '{concept.catalog.construction.name}'. "
                    f"El concepto '{concept.description}' pertenece a una obra no asignada."
                )
        
        # Si tiene permisos o es staff, crear el avance
        serializer.save()
    
class PhysicalDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para obtener, actualizar o eliminar un avance físico específico.
    GET: Obtiene un avance por su ID
    PUT/PATCH: Actualiza un avance
    DELETE: Elimina un avance
    """
    queryset = Physical.objects.all()
    serializer_class = PhysicalSerializer
    
    def get_queryset(self):
        """
        Filtrar avances según las obras asignadas al usuario autenticado
        """
        user = self.request.user
        queryset = super().get_queryset()
        
        # Filtrar por permisos de usuario (solo obras asignadas)
        if user.is_authenticated and not user.is_staff:
            from obra.models import UserConstruction
            
            # Obtener IDs de construcciones asignadas al usuario
            user_constructions = UserConstruction.objects.filter(
                user=user,
                is_active=True
            ).values_list('construction', flat=True)
            
            # Filtrar avances solo de conceptos que pertenecen a obras asignadas
            queryset = queryset.filter(
                concept__catalog__construction__in=user_constructions
            )
        
        return queryset

    def perform_update(self, serializer):
        """
        Validar permisos y registrar cambios de estado en el historial
        """
        user = self.request.user
        instance = self.get_object()
        old_status = instance.status
        
        # Validar si se está cambiando el concepto (no debería permitirse normalmente)
        if 'concept' in serializer.validated_data:
            new_concept = serializer.validated_data['concept']
            
            # Solo validar si el usuario no es staff
            if user.is_authenticated and not user.is_staff:
                from obra.models import UserConstruction
                
                # Verificar acceso al nuevo concepto
                has_access = UserConstruction.objects.filter(
                    user=user,
                    construction=new_concept.catalog.construction,
                    is_active=True
                ).exists()
                
                if not has_access:
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied(
                        f"No tienes permisos para asignar el concepto '{new_concept.description}' "
                        f"que pertenece a la obra '{new_concept.catalog.construction.name}'"
                    )
        
        # Actualizar el avance
        updated_instance = serializer.save()
        
        # Si cambió el status, registrar en historial
        if old_status != updated_instance.status:
            PhysicalStatusHistory.objects.create(
                physical=updated_instance,
                previous_status=old_status,
                new_status=updated_instance.status,
                changed_by=self.request.user if self.request.user.is_authenticated else None
            )

class PhysicalProgressSummaryView(APIView):
    def get(self, request):
        # Parámetros de filtrado
        concept = request.query_params.get('concept')
        work_item = request.query_params.get('work_item')
        catalog = request.query_params.get('catalog')
        schedule_id = request.query_params.get('schedule')
        period_start = request.query_params.get('period_start')
        period_end = request.query_params.get('period_end')
        
        # Paginación
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 50))
        
        # Si no se proporcionan fechas, usar el mes actual
        if not period_start or not period_end:
            today = datetime.now().date()
            period_start = today.replace(day=1)
            next_month = today.replace(day=28) + timedelta(days=4)
            period_end = next_month.replace(day=1) - timedelta(days=1)
        else:
            # Convertir a objetos date si vienen como strings
            period_start = datetime.strptime(period_start, '%Y-%m-%d').date() if isinstance(period_start, str) else period_start
            period_end = datetime.strptime(period_end, '%Y-%m-%d').date() if isinstance(period_end, str) else period_end
        
        # Filtrar conceptos según parámetros
        concepts_query = Concept.objects.filter(is_active=True)
        
        if concept:
            concepts_query = concepts_query.filter(id=concept)
        if work_item:
            concepts_query = concepts_query.filter(work_item_id=work_item)
        if catalog:
            concepts_query = concepts_query.filter(catalog_id=catalog)
        
        # Buscar programación (de cronograma o estimación planificada)
        programmed_volumes = {}
        programmed_found = False
        program_source = None
        
        # 1. Buscar en cronograma específico si se proporciona
        if schedule_id:
            try:
                schedule = Schedule.objects.get(id=schedule_id)
                program_source = f"Cronograma: {schedule.name}"
                
                activities = Activity.objects.filter(
                    schedule=schedule,
                    start_date__lte=period_end,
                    end_date__gte=period_start
                ).prefetch_related('activity_concepts__concept')
                
                for activity in activities:
                    # Calcular proporción en el período
                    activity_start = max(activity.start_date, period_start)
                    activity_end = min(activity.end_date, period_end)
                    days_in_period = (activity_end - activity_start).days + 1
                    total_activity_days = (activity.end_date - activity.start_date).days + 1
                    
                    if total_activity_days > 0:
                        percentage_in_period = days_in_period / total_activity_days
                    else:
                        percentage_in_period = 0
                    
                    for ac in activity.activity_concepts.all():
                        if not concepts_query.filter(id=ac.concept.id).exists():
                            continue
                            
                        concept_id = ac.concept.id
                        if concept_id in programmed_volumes:
                            programmed_volumes[concept_id] += ac.concept.quantity * percentage_in_period
                        else:
                            programmed_volumes[concept_id] = ac.concept.quantity * percentage_in_period
                
                if programmed_volumes:
                    programmed_found = True
            except Schedule.DoesNotExist:
                pass
        
        # 2. Si no hay cronograma específico o está vacío, buscar cronogramas activos
        if not programmed_found and not schedule_id:
            # Buscar cronogramas activos que coincidan con el período
            schedules = Schedule.objects.filter(
                is_active=True,
                construction__in=concepts_query.values_list('catalog__construction', flat=True).distinct()
            )
            
            for schedule in schedules:
                activities = Activity.objects.filter(
                    schedule=schedule,
                    start_date__lte=period_end,
                    end_date__gte=period_start
                ).prefetch_related('activity_concepts__concept')
                
                if activities.exists():
                    program_source = f"Cronograma: {schedule.name}"
                    
                    for activity in activities:
                        # Cálculos de proporción (igual que arriba)
                        activity_start = max(activity.start_date, period_start)
                        activity_end = min(activity.end_date, period_end)
                        days_in_period = (activity_end - activity_start).days + 1
                        total_activity_days = (activity.end_date - activity.start_date).days + 1
                        
                        if total_activity_days > 0:
                            percentage_in_period = days_in_period / total_activity_days
                        else:
                            percentage_in_period = 0
                        
                        for ac in activity.activity_concepts.all():
                            if not concepts_query.filter(id=ac.concept.id).exists():
                                continue
                                
                            concept_id = ac.concept.id
                            if concept_id in programmed_volumes:
                                programmed_volumes[concept_id] += ac.concept.quantity * percentage_in_period
                            else:
                                programmed_volumes[concept_id] = ac.concept.quantity * percentage_in_period
                    
                    if programmed_volumes:
                        programmed_found = True
                        break  # Una vez que encontramos un cronograma válido, salimos
        
        # 3. Si aún no hay programación, buscar en estimaciones planificadas
        if not programmed_found:
            planned_estimations = Estimation.objects.filter(
                is_planned=True,
                period_start__lte=period_end,
                period_end__gte=period_start
            )
            
            if catalog:
                construction_ids = concepts_query.values_list('catalog__construction', flat=True).distinct()
                planned_estimations = planned_estimations.filter(construction__in=construction_ids)
            
            for estimation in planned_estimations:
                details = EstimationDetail.objects.filter(estimation=estimation)
                
                if concept:
                    details = details.filter(concept_id=concept)
                if work_item:
                    details = details.filter(concept__work_item_id=work_item)
                if catalog:
                    details = details.filter(concept__catalog_id=catalog)
                
                if details.exists():
                    program_source = f"Estimación planificada: {estimation.name}"
                    
                    for detail in details:
                        if not concepts_query.filter(id=detail.concept.id).exists():
                            continue
                            
                        concept_id = detail.concept.id
                        if concept_id in programmed_volumes:
                            programmed_volumes[concept_id] += detail.volume
                        else:
                            programmed_volumes[concept_id] = detail.volume
                    
                    if programmed_volumes:
                        programmed_found = True
                        break
        
        # Obtener avances ejecutados en el período especificado
        executed_volumes = {}
        for concept in concepts_query:
            executed_volume = Physical.objects.filter(
                concept=concept,
                status='APPROVED',
                date__gte=period_start,
                date__lte=period_end
            ).aggregate(total=Sum('volume'))['total'] or 0
            
            if executed_volume > 0:
                executed_volumes[concept.id] = executed_volume

        approval_info = {}
        for concept_id in executed_volumes.keys():
            # Obtener último avance aprobado para este concepto
            latest_approvals = PhysicalStatusHistory.objects.filter(
                physical__concept_id=concept_id,
                new_status='APPROVED',
                physical__date__gte=period_start,
                physical__date__lte=period_end
            ).order_by('-changed_at')
            
            if latest_approvals.exists():
                latest = latest_approvals.first()
                original_date = latest.physical.date
                approval_date = latest.changed_at.date()
                days_to_approve = (approval_date - original_date).days
                
                approval_info[concept_id] = {
                    'submission_date': original_date.strftime('%Y-%m-%d'),
                    'approval_date': approval_date.strftime('%Y-%m-%d'),
                    'days_to_approve': days_to_approve
                }

        # Filtrar conceptos relevantes (con programación o ejecución)
        concepts_with_execution = set(executed_volumes.keys())
        concepts_with_programming = set(programmed_volumes.keys())
        relevant_concept_ids = concepts_with_execution.union(concepts_with_programming)
        
        # Si no hay conceptos relevantes pero hay query, mantenemos la query original
        if relevant_concept_ids or not (concept or work_item or catalog):
            filtered_concepts = concepts_query.filter(id__in=relevant_concept_ids)
        else:
            filtered_concepts = concepts_query
        
        # Contar total antes de paginar
        total_count = filtered_concepts.count()
        
        # Aplicar paginación
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        paginated_concepts = filtered_concepts[start_index:end_index]
        
        # Calcular totales monetarios y preparar detalles
        total_programmed_amount = 0
        total_executed_amount = 0
        details = []
        completed_concepts = 0
        
        # Obtener totales globales para cálculo de porcentajes
        global_total = sum(concept.quantity * concept.unit_price for concept in concepts_query)
        
        for concept in paginated_concepts:
            # Volúmenes programados y ejecutados
            programmed_volume = programmed_volumes.get(concept.id, 0)
            executed_volume = executed_volumes.get(concept.id, 0)
            
            # Importes monetarios
            programmed_amount = programmed_volume * concept.unit_price
            executed_amount = executed_volume * concept.unit_price
            
            # Acumular totales
            total_programmed_amount += programmed_amount
            total_executed_amount += executed_amount
            
            # Porcentaje de avance para este concepto
            progress_percentage = 0
            if programmed_volume > 0:
                progress_percentage = (executed_volume / programmed_volume) * 100
                if progress_percentage >= 100:
                    completed_concepts += 1
            
            # Porcentaje global (con respecto a toda la obra)
            global_percentage = 0
            if concept.quantity > 0:
                global_percentage = (executed_volume / concept.quantity) * 100
            
            # Porcentaje financiero global
            financial_global_percentage = 0
            if global_total > 0:
                financial_global_percentage = (executed_amount / (concept.quantity * concept.unit_price)) * 100
            
            details.append({
                'id': concept.id,
                'description': concept.description,
                'unit': concept.unit,
                'quantity': concept.quantity,
                'unit_price': concept.unit_price, 
                'programmed_volume': programmed_volume,
                'programmed_amount': programmed_amount,
                'executed_volume': executed_volume,
                'executed_amount': executed_amount,
                'approval_info': approval_info.get(concept.id, None),
                'progress_percentage': progress_percentage,
                'global_percentage': global_percentage,
                'financial_global_percentage': financial_global_percentage
            })
        
        # Calcular porcentajes globales
        period_percentage = 0
        if total_programmed_amount > 0:
            period_percentage = (total_executed_amount / total_programmed_amount) * 100
        
        # Datos para gráfica por semanas
        weeks = {}
        weekly_start = period_start
        
        # Crear semanas dentro del período solicitado
        while weekly_start <= period_end:
            week_end = min(weekly_start + timedelta(days=6), period_end)
            week_name = f"Semana {weekly_start.strftime('%d/%m')}"
            
            # Datos ejecutados para esta semana
            week_progress = Physical.objects.filter(
                status='APPROVED',
                date__gte=weekly_start,
                date__lte=week_end
            )
            
            if concept:
                week_progress = week_progress.filter(concept_id=concept)
            if work_item:
                week_progress = week_progress.filter(concept__work_item_id=work_item)
            if catalog:
                week_progress = week_progress.filter(concept__catalog_id=catalog)
            
            # Calcular avance financiero semanal
            week_amount = 0
            week_volume = week_progress.aggregate(total=Sum('volume'))['total'] or 0
            
            for execution in week_progress.values('concept_id', 'volume'):
                try:
                    concept_obj = Concept.objects.get(id=execution['concept_id'])
                    week_amount += execution['volume'] * concept_obj.unit_price
                except Concept.DoesNotExist:
                    pass
            
            weeks[week_name] = {
                'start_date': weekly_start.strftime('%Y-%m-%d'),
                'end_date': week_end.strftime('%Y-%m-%d'),
                'executed_volume': float(week_volume),
                'executed_amount': float(week_amount)
            }
            
            # Avanzar a la siguiente semana
            weekly_start = week_end + timedelta(days=1)
        
        # Preparar respuesta
        response_data = {
            'period': {
                'start_date': period_start.strftime('%Y-%m-%d'),
                'end_date': period_end.strftime('%Y-%m-%d'),
            },
            'summary': {
                'total_programmed_amount': float(total_programmed_amount),
                'total_executed_amount': float(total_executed_amount),
                'period_percentage': float(period_percentage),
                'concepts_count': total_count,  # Usar total_count en lugar de concepts_query.count()
                'completed_concepts': completed_concepts,
            },
            'details': details,
            'chart_data': {
                'weeks': weeks,
            },
            'pagination': {
                'total_items': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': (total_count + page_size - 1) // page_size
            }
        }
        
        # Añadir mensaje si no hay programación
        if not programmed_found:
            response_data['program_status'] = "no_program"
            response_data['message'] = "Aún no se ha creado el programa"
        else:
            response_data['program_status'] = "program_found"
            response_data['program_source'] = program_source
        
        return Response(response_data)
    
class ApprovalAnalyticsView(APIView):
    def get(self, request):
        # Obtener promedio de días para aprobación
        approvals = PhysicalStatusHistory.objects.filter(
            new_status='APPROVED',
            previous_status='PENDING'
        ).annotate(
            days_taken=Extract(F('changed_at') - F('physical__date'), 'day')
        )
        
        avg_days = approvals.aggregate(avg=Avg('days_taken'))['avg'] or 0
        
        # Mensaje motivacional basado en análisis
        message = f"Utilizando nuestro servicio, el tiempo promedio de respuesta es de {avg_days:.1f} días, agilizando la ejecución de la obra."
        
        return Response({
            'avg_approval_time': avg_days,
            'total_approvals': approvals.count(),
            'message': message
        })
    
class EstimationListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar y crear estimaciones (avance financiero)
    """
    queryset = Estimation.objects.all()
    serializer_class = EstimationSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status']
    ordering_fields = ['period_start', 'period_end', 'total_amount']
    ordering = ['-period_end']  # Más reciente primero
    
    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()
        
        # Filtrar por obras asignadas al usuario
        if user.is_authenticated and not user.is_staff:
            from obra.models import UserConstruction
            user_constructions = UserConstruction.objects.filter(
                user=user,
                is_active=True
            ).values_list('construction', flat=True)
            queryset = queryset.filter(construction__in=user_constructions)
        
        return queryset
    
    def perform_create(self, serializer):
        """
        Al crear, guarda primero sin total y luego actualiza el total
        """
        instance = serializer.save()
        # El total se actualizará cuando se agreguen detalles

class EstimationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para obtener, actualizar o eliminar una estimación
    """
    queryset = Estimation.objects.all()
    serializer_class = EstimationSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()
        
        # Filtrar por obras asignadas al usuario
        if user.is_authenticated and not user.is_staff:
            from obra.models import UserConstruction
            user_constructions = UserConstruction.objects.filter(
                user=user,
                is_active=True
            ).values_list('construction', flat=True)
            queryset = queryset.filter(construction__in=user_constructions)
        
        return queryset

class EstimationItemListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar y crear detalles de estimación
    """
    queryset = EstimationDetail.objects.all()
    serializer_class = EstimationDetailSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['estimation', 'concept']
    
    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()
        
        # Filtrar por obras asignadas al usuario (a través de estimation.construction)
        if user.is_authenticated and not user.is_staff:
            from obra.models import UserConstruction
            user_constructions = UserConstruction.objects.filter(
                user=user,
                is_active=True
            ).values_list('construction', flat=True)
            queryset = queryset.filter(estimation__construction__in=user_constructions)
        
        return queryset
    
    def perform_create(self, serializer):
        """
        Al crear un detalle, actualiza el total de la estimación
        """
        detail = serializer.save()
        # Actualizar el total de la estimación
        estimation = detail.estimation
        estimation.update_total()

class EstimationItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para obtener, actualizar o eliminar un detalle de estimación
    """
    queryset = EstimationDetail.objects.all()
    serializer_class = EstimationDetailSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()
        
        # Filtrar por obras asignadas al usuario (a través de estimation.construction)
        if user.is_authenticated and not user.is_staff:
            from obra.models import UserConstruction
            user_constructions = UserConstruction.objects.filter(
                user=user,
                is_active=True
            ).values_list('construction', flat=True)
            queryset = queryset.filter(estimation__construction__in=user_constructions)
        
        return queryset
    
    def perform_update(self, serializer):
        """Al actualizar, recalcular el total de la estimación"""
        detail = serializer.save()
        detail.estimation.update_total()
        
    def perform_destroy(self, instance):
        """Al eliminar, recalcular el total de la estimación"""
        estimation = instance.estimation
        instance.delete()
        estimation.update_total()

class ProgressDashboardView(APIView):
    def get(self, request):
        # Filtros posibles
        catalog_id = request.query_params.get('catalog')
        work_item_id = request.query_params.get('work_item')
        schedule_id = request.query_params.get('schedule')  # Añadido para poder seleccionar cronograma específico
        period_start = request.query_params.get('period_start')
        period_end = request.query_params.get('period_end')
        
        # Si no se proporcionan fechas, usar el mes actual
        if not period_start or not period_end:
            today = datetime.now().date()
            period_start = today.replace(day=1)
            next_month = today.replace(day=28) + timedelta(days=4)
            period_end = next_month.replace(day=1) - timedelta(days=1)
        else:
            period_start = datetime.strptime(period_start, '%Y-%m-%d').date() if isinstance(period_start, str) else period_start
            period_end = datetime.strptime(period_end, '%Y-%m-%d').date() if isinstance(period_end, str) else period_end
        
        # Base query - todos los conceptos activos
        concepts_query = Concept.objects.filter(is_active=True)
        
        # Aplicar filtros
        if catalog_id:
            concepts_query = concepts_query.filter(catalog_id=catalog_id)
        if work_item_id:
            concepts_query = concepts_query.filter(work_item_id=work_item_id)
        
        # Buscar programación desde cronograma
        programmed_volumes = {}
        programmed_found = False
        program_source = None
        
        # 1. Buscar en cronograma específico si se proporciona
        if schedule_id:
            try:
                schedule = Schedule.objects.get(id=schedule_id)
                program_source = f"Cronograma: {schedule.name}"
                
                activities = Activity.objects.filter(
                    schedule=schedule,
                    start_date__lte=period_end,
                    end_date__gte=period_start
                ).prefetch_related('activity_concepts__concept')
                
                for activity in activities:
                    # Calcular proporción en el período
                    activity_start = max(activity.start_date, period_start)
                    activity_end = min(activity.end_date, period_end)
                    days_in_period = (activity_end - activity_start).days + 1
                    total_activity_days = (activity.end_date - activity.start_date).days + 1
                    
                    if total_activity_days > 0:
                        percentage_in_period = days_in_period / total_activity_days
                    else:
                        percentage_in_period = 0
                    
                    for ac in activity.activity_concepts.all():
                        if not concepts_query.filter(id=ac.concept.id).exists():
                            continue
                            
                        concept_id = ac.concept.id
                        if concept_id in programmed_volumes:
                            programmed_volumes[concept_id] += ac.concept.quantity * percentage_in_period
                        else:
                            programmed_volumes[concept_id] = ac.concept.quantity * percentage_in_period
                
                if programmed_volumes:
                    programmed_found = True
            except Schedule.DoesNotExist:
                pass
        
        # 2. Si no hay cronograma específico, buscar cronogramas activos
        if not programmed_found and not schedule_id:
            # Buscar cronogramas activos
            schedules = Schedule.objects.filter(
                is_active=True,
                construction__in=concepts_query.values_list('catalog__construction', flat=True).distinct()
            )
            
            for schedule in schedules:
                activities = Activity.objects.filter(
                    schedule=schedule,
                    start_date__lte=period_end,
                    end_date__gte=period_start
                ).prefetch_related('activity_concepts__concept')
                
                if activities.exists():
                    program_source = f"Cronograma: {schedule.name}"
                    
                    for activity in activities:
                        # Cálculos de proporción
                        activity_start = max(activity.start_date, period_start)
                        activity_end = min(activity.end_date, period_end)
                        days_in_period = (activity_end - activity_start).days + 1
                        total_activity_days = (activity.end_date - activity.start_date).days + 1
                        
                        if total_activity_days > 0:
                            percentage_in_period = days_in_period / total_activity_days
                        else:
                            percentage_in_period = 0
                        
                        for ac in activity.activity_concepts.all():
                            if not concepts_query.filter(id=ac.concept.id).exists():
                                continue
                                
                            concept_id = ac.concept.id
                            if concept_id in programmed_volumes:
                                programmed_volumes[concept_id] += ac.concept.quantity * percentage_in_period
                            else:
                                programmed_volumes[concept_id] = ac.concept.quantity * percentage_in_period
                    
                    if programmed_volumes:
                        programmed_found = True
                        break
        
        # Datos físicos y financieros
        # Prefetch datos físicos
        concept_ids = list(concepts_query.values_list('id', flat=True))
        physical_advances = Physical.objects.filter(
            concept_id__in=concept_ids,
            status='APPROVED'
        ).values('concept_id').annotate(
            total_volume=Sum('volume')
        )
        
        physical_volumes = {adv['concept_id']: adv['total_volume'] for adv in physical_advances}
        
        # Datos financieros
        financial_advances = EstimationDetail.objects.filter(
            concept_id__in=concept_ids,
            estimation__status__in=['APPROVED', 'PAID']
        ).values('concept_id').annotate(
            total_volume=Sum('volume'),
            total_amount=Sum('amount')
        )
        
        financial_volumes = {}
        financial_amounts = {}
        for adv in financial_advances:
            financial_volumes[adv['concept_id']] = adv['total_volume']
            financial_amounts[adv['concept_id']] = adv['total_amount']
        
        # Calcular totales
        total_programmed_amount = 0
        total_physical_amount = 0
        total_financial_amount = 0
        
        physical_data = {}
        financial_data = {}
        programmed_data = {}
        
        for concept in concepts_query:
            # Valores programados para el período
            programmed_volume = programmed_volumes.get(concept.id, 0)
            programmed_amount = programmed_volume * concept.unit_price
            total_programmed_amount += programmed_amount
            
            # Avance físico
            physical_volume = physical_volumes.get(concept.id, 0) or 0
            physical_amount = physical_volume * concept.unit_price
            total_physical_amount += physical_amount
            
            # Avance financiero
            financial_volume = financial_volumes.get(concept.id, 0) or 0
            financial_amount = financial_amounts.get(concept.id, 0) or 0
            total_financial_amount += financial_amount
            
            # Porcentajes - solo calcular si hay programación
            physical_percentage = 0
            financial_percentage = 0
            
            if programmed_amount > 0:
                physical_percentage = (physical_amount / programmed_amount) * 100
                financial_percentage = (financial_amount / programmed_amount) * 100
            
            programmed_data[concept.id] = {
                'volume': programmed_volume,
                'amount': programmed_amount,
            }
            
            physical_data[concept.id] = {
                'volume': physical_volume,
                'amount': physical_amount,
                'percentage': physical_percentage
            }
            
            financial_data[concept.id] = {
                'volume': financial_volume,
                'amount': financial_amount,
                'percentage': financial_percentage
            }
        
        # Porcentajes globales
        physical_percentage = 0
        financial_percentage = 0
        
        if total_programmed_amount > 0:
            physical_percentage = (total_physical_amount / total_programmed_amount) * 100
            financial_percentage = (total_financial_amount / total_programmed_amount) * 100
        
        # Datos mensuales
        months_data = {}
        current_date = period_start
        month_count = 0
        
        while current_date <= period_end and month_count < 12:
            month_name = current_date.strftime('%Y-%m')
            month_end = min((current_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1), period_end)

            # Datos programados para el mes
            month_programmed_amount = 0
            if programmed_found:
                # Filtrar actividades que caen en este mes
                month_activities = Activity.objects.filter(
                    schedule__is_active=True if not schedule_id else Q(schedule_id=schedule_id),
                    start_date__lte=month_end,
                    end_date__gte=current_date
                ).prefetch_related('activity_concepts__concept')
                
                # Calcular proporciones
                for activity in month_activities:
                    # Solo considerar actividades relevantes para los conceptos filtrados
                    activity_start = max(activity.start_date, current_date)
                    activity_end = min(activity.end_date, month_end)
                    days_in_period = (activity_end - activity_start).days + 1
                    total_activity_days = (activity.end_date - activity.start_date).days + 1
                    
                    if total_activity_days > 0:
                        percentage_in_period = days_in_period / total_activity_days
                        
                        for ac in activity.activity_concepts.all():
                            if ac.concept_id in concept_ids:
                                month_programmed_amount += ac.concept.quantity * percentage_in_period * ac.concept.unit_price
            
            # Datos físicos para el mes
            physical_progress = Physical.objects.filter(
                concept__in=concepts_query,
                status='APPROVED',
                date__gte=current_date,
                date__lte=month_end
            ).select_related('concept')
            
            month_physical_amount = 0
            for progress in physical_progress:
                month_physical_amount += progress.volume * progress.concept.unit_price
            
            # Datos financieros para el mes
            financial_progress = EstimationDetail.objects.filter(
                concept__in=concepts_query,
                estimation__status__in=['APPROVED', 'PAID'],
                estimation__period_start__gte=current_date,
                estimation__period_end__lte=month_end
            )
            
            month_financial_amount = financial_progress.aggregate(total=Sum('amount'))['total'] or 0
            
            # Calcular porcentajes solo si hay programación
            total_catalog_amount = sum(concept.quantity * concept.unit_price for concept in concepts_query)
            programmed_percentage = 0
            if total_catalog_amount > 0:
                programmed_percentage = (total_programmed_amount / total_catalog_amount) * 100

            month_physical_percentage = 0
            month_financial_percentage = 0
            
            if total_programmed_amount > 0:
                month_physical_percentage = (month_physical_amount / total_programmed_amount) * 100
                month_financial_percentage = (month_financial_amount / total_programmed_amount) * 100
            
            months_data[month_name] = {
                'programmed': {
                    'amount': float(month_programmed_amount),
                    'percentage': float((month_programmed_amount / total_programmed_amount) * 100) if total_programmed_amount > 0 else 0.0
                },
                'physical': {
                    'amount': float(month_physical_amount),
                    'percentage': float(month_physical_percentage)
                },
                'financial': {
                    'amount': float(month_financial_amount),
                    'percentage': float(month_financial_percentage)
                }
            }
            
            # Avanzar al siguiente mes
            next_month = current_date.replace(day=28) + timedelta(days=4)
            current_date = next_month.replace(day=1)
            
            month_count += 1
        
        # Detalles por concepto
        details = []
        for concept in concepts_query:
            programmed_info = programmed_data.get(concept.id, {'volume': 0, 'amount': 0})
            physical_info = physical_data.get(concept.id, {'volume': 0, 'percentage': 0, 'amount': 0})
            financial_info = financial_data.get(concept.id, {'volume': 0, 'percentage': 0, 'amount': 0})
            
            details.append({
                'id': concept.id,
                'description': concept.description,
                'unit': concept.unit,
                'quantity': concept.quantity,
                'unit_price': concept.unit_price,
                'programmed_volume': programmed_info['volume'],
                'programmed_amount': programmed_info['amount'],
                'physical_volume': physical_info['volume'],
                'physical_percentage': physical_info['percentage'],
                'physical_amount': physical_info['amount'],
                'financial_volume': financial_info['volume'],
                'financial_percentage': financial_info['percentage'],
                'financial_amount': financial_info['amount']
            })
        
        # Preparar respuesta
        response_data = {
            'summary': {
                'programmed': {
                    'amount': float(total_programmed_amount),
                    'percentage': float(programmed_percentage)
                },
                'physical': {
                    'amount': float(total_physical_amount),
                    'percentage': float(physical_percentage)
                },
                'financial': {
                    'amount': float(total_financial_amount),
                    'percentage': float(financial_percentage)
                },
                'difference': {
                    'amount': float(total_physical_amount - total_financial_amount),
                    'percentage': float(physical_percentage - financial_percentage)
                }
            },
            'chart_data': {
                'months': months_data
            },
            'details': details
        }
        
        # Añadir mensaje si no hay programación
        if not programmed_found:
            response_data['program_status'] = "no_program"
            response_data['message'] = "Aún no se ha creado el programa"
        else:
            response_data['program_status'] = "program_found"
            response_data['program_source'] = program_source
        
        return Response(response_data)

class EstimationPlanningViewSet(viewsets.ModelViewSet):
    """ViewSet para planificación de estimaciones con integración a cronogramas"""
    queryset = Estimation.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['name', 'construction__name']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return EstimationListSerializer
        elif self.action in ['retrieve', 'import_from_schedule', 'compare_with_real']:
            return EstimationDetailedSerializer
        return EstimationSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = Estimation.objects.all()
        
        # Filtrar por obras asignadas al usuario
        if user.is_authenticated and not user.is_staff:
            from obra.models import UserConstruction
            user_constructions = UserConstruction.objects.filter(
                user=user,
                is_active=True
            ).values_list('construction', flat=True)
            queryset = queryset.filter(construction__in=user_constructions)
        
        # Filtrar por obra
        construction_id = self.request.query_params.get('construction_id')
        if construction_id:
            queryset = queryset.filter(construction_id=construction_id)
        
        # Filtrar por tipo (planificada o real)
        is_planned = self.request.query_params.get('is_planned')
        if is_planned is not None:
            is_planned = is_planned.lower() == 'true'
            queryset = queryset.filter(is_planned=is_planned)
        
        # Filtrar por estado
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Precargar relaciones para optimizar consultas
        queryset = queryset.select_related('construction', 'schedule', 'created_by')
        
        return queryset
    
    def perform_create(self, serializer):
        # Asignar el usuario actual como creador si está autenticado
        if self.request.user and self.request.user.is_authenticated:
            serializer.save(created_by=self.request.user)
        else:
            serializer.save()
    
    @action(detail=False, methods=['post'])
    def import_from_schedule(self, request):
        """Endpoint para crear una estimación basada en un cronograma"""
        # Obtener datos necesarios
        construction_id = request.data.get('construction_id')
        schedule_id = request.data.get('schedule_id')
        period_start = request.data.get('period_start')
        period_end = request.data.get('period_end')
        name = request.data.get('name')
        
        if not all([construction_id, schedule_id, period_start, period_end, name]):
            return Response({
                "error": "Se requieren construction_id, schedule_id, period_start, period_end y name"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            construction = Construction.objects.get(id=construction_id)
            schedule = Schedule.objects.get(id=schedule_id)
        except (Construction.DoesNotExist, Schedule.DoesNotExist):
            return Response({
                "error": "Construcción o cronograma no encontrados"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Crear la estimación
        estimation = Estimation.objects.create(
            name=name,
            period_start=period_start,
            period_end=period_end,
            construction=construction,
            is_planned=True,
            based_on_schedule=True,
            schedule=schedule,
            created_by=request.user if request.user.is_authenticated else None,
            status='DRAFT'
        )
        
        # Buscar actividades en el cronograma que se superpongan con el período
        activities = Activity.objects.filter(
            schedule=schedule,
            start_date__lte=period_end,
            end_date__gte=period_start
        ).prefetch_related('activity_concepts__concept')
        
        # Generar detalles de estimación para cada concepto en esas actividades
        details_created = 0
        
        for activity in activities:
            # Calcular días dentro del período
            activity_start = max(activity.start_date, period_start)
            activity_end = min(activity.end_date, period_end)
            days_in_period = (activity_end - activity_start).days + 1
            
            # Calcular días totales de la actividad
            total_activity_days = (activity.end_date - activity.start_date).days + 1
            
            # Si la actividad completa está en el período, usar 100%
            if days_in_period >= total_activity_days:
                percentage_in_period = 1.0
            else:
                percentage_in_period = days_in_period / total_activity_days
            
            # Calcular fecha promedio de ejecución para este período
            mid_date = activity_start + timedelta(days=days_in_period // 2)
            
            # Crear detalles para cada concepto en esta actividad
            for activity_concept in activity.activity_concepts.all():
                concept = activity_concept.concept
                
                # Calcular volumen proporcional para este período
                planned_volume = concept.quantity * percentage_in_period
                
                # Calcular importe
                amount = planned_volume * concept.unit_price
                
                # Crear detalle de estimación
                EstimationDetail.objects.create(
                    estimation=estimation,
                    concept=concept,
                    volume=planned_volume,
                    amount=amount,
                    execution_date=mid_date,
                    commitment_status='PENDING',
                    activity=activity,
                    imported_from_schedule=True
                )
                
                details_created += 1
        
        # Actualizar total de la estimación
        estimation.update_total()
        
        return Response({
            "id": estimation.id,
            "name": estimation.name,
            "details_created": details_created,
            "total_amount": estimation.total_amount
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def compare_with_real(self, request, pk=None):
        """Endpoint para comparar estimación planificada vs. avance real"""
        estimation = self.get_object()
        
        if not estimation.is_planned:
            return Response({
                "error": "Esta función solo está disponible para estimaciones planificadas"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = []
        
        for detail in estimation.details.all():
            # Buscar avances reales para este concepto en el período
            real_progress = Physical.objects.filter(
                concept=detail.concept,
                date__gte=estimation.period_start,
                date__lte=estimation.period_end,
                status='APPROVED'
            ).aggregate(total_volume=Sum('volume'))['total_volume'] or 0
            
            # Calcular la diferencia porcentual
            if detail.volume > 0:
                variance_percentage = ((real_progress - detail.volume) / detail.volume) * 100
            else:
                variance_percentage = 0 if real_progress == 0 else 100
            
            # Determinar el estado
            if real_progress == 0:
                status_value = 'NO_PROGRESS'
            elif real_progress >= detail.volume:
                status_value = 'COMPLETED'
            elif real_progress > 0:
                status_value = 'PARTIAL'
            
            result.append({
                'detail_id': detail.id,
                'concept': detail.concept.description,
                'planned_volume': detail.volume,
                'real_volume': real_progress,
                'variance': real_progress - detail.volume,
                'variance_percentage': variance_percentage,
                'status': status_value
            })
        
        return Response(result)
    
    @action(detail=True, methods=['post'])
    def update_commitments(self, request, pk=None):
        """Endpoint para actualizar estado de compromisos en una estimación"""
        estimation = self.get_object()
        detail_ids = request.data.get('detail_ids', [])
        new_status = request.data.get('status')
        
        if not new_status or not detail_ids:
            return Response({
                "error": "Se requieren detail_ids y status"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validar que el estado sea válido
        valid_statuses = ['PENDING', 'COMMITTED', 'EXECUTED', 'DELAYED']
        if new_status not in valid_statuses:
            return Response({
                "error": f"Estado inválido. Debe ser uno de: {', '.join(valid_statuses)}"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Actualizar estado de los detalles
        updated = EstimationDetail.objects.filter(
            estimation=estimation,
            id__in=detail_ids
        ).update(commitment_status=new_status)
        
        return Response({
            "updated_count": updated
        })

class CommitmentTrackingViewSet(viewsets.ModelViewSet):
    """ViewSet para seguimiento detallado de compromisos"""
    queryset = CommitmentTracking.objects.all()
    serializer_class = CommitmentTrackingSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['estimation_detail', 'status']
    
    def get_queryset(self):
        queryset = CommitmentTracking.objects.all()
        
        # Filtrar por detalle de estimación
        estimation_detail_id = self.request.query_params.get('estimation_detail_id')
        if estimation_detail_id:
            queryset = queryset.filter(estimation_detail_id=estimation_detail_id)
        
        # Filtrar por estimación
        estimation_id = self.request.query_params.get('estimation_id')
        if estimation_id:
            queryset = queryset.filter(estimation_detail__estimation_id=estimation_id)
        
        # Filtrar por fecha planificada
        planned_date_start = self.request.query_params.get('planned_date_start')
        planned_date_end = self.request.query_params.get('planned_date_end')
        if planned_date_start and planned_date_end:
            queryset = queryset.filter(planned_date__gte=planned_date_start, planned_date__lte=planned_date_end)
        
        return queryset