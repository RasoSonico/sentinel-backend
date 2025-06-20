# avance/serializers.py (modificaciones)
from rest_framework import serializers
from .models import Physical, Estimation, EstimationDetail, CommitmentTracking, PhysicalStatusHistory
from catalogo.models import Concept
from catalogo.serializers import ConceptSerializer
from cronograma.serializers import ActivitySerializer

class PhysicalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Physical
        fields = ['id', 'concept', 'volume', 'date', 'status', 'comments']
    
    # validaciones
    def validate_volume(self, value):
        if value <= 0:
            raise serializers.ValidationError("El volumen debe ser mayor que cero.")
        return value
    
    def validate_status(self, value):
        valid_statuses = ['PENDING', 'APPROVED', 'REJECTED']
        if value not in valid_statuses:
            raise serializers.ValidationError("Estado no válido.")
        return value
    
    def validate_concept(self, value):
        if not Concept.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("El concepto no existe.")
        return value
    
# avance/serializers.py - añadir este serializer
class PhysicalStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PhysicalStatusHistory
        fields = ['id', 'physical', 'previous_status', 'new_status', 'changed_at', 'changed_by']
        read_only_fields = ['id', 'changed_at']

class CommitmentTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommitmentTracking
        fields = [
            'id', 'estimation_detail', 'planned_date', 'actual_date',
            'planned_volume', 'actual_volume', 'variance_percentage',
            'status', 'comments', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'variance_percentage', 'created_at', 'updated_at']
    
    def validate(self, data):
        if 'actual_volume' in data and data['actual_volume'] is not None:
            if data['actual_volume'] < 0:
                raise serializers.ValidationError("El volumen real no puede ser negativo.")
        
        if 'planned_volume' in data and data['planned_volume'] <= 0:
            raise serializers.ValidationError("El volumen planificado debe ser mayor que cero.")
        
        return data
    
    def create(self, validated_data):
        # Calculo de desviación
        if 'actual_volume' in validated_data and validated_data['actual_volume'] is not None:
            planned = validated_data['planned_volume']
            actual = validated_data['actual_volume']
            if planned > 0:
                variance = ((actual - planned) / planned) * 100
                validated_data['variance_percentage'] = variance
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        # Recalcular desviación si cambia algún volumen
        planned = validated_data.get('planned_volume', instance.planned_volume)
        actual = validated_data.get('actual_volume', instance.actual_volume)
        
        if actual is not None and planned > 0:
            variance = ((actual - planned) / planned) * 100
            validated_data['variance_percentage'] = variance
        
        return super().update(instance, validated_data)

class EstimationDetailSerializer(serializers.ModelSerializer):
    concept_detail = ConceptSerializer(source='concept', read_only=True)
    activity_detail = ActivitySerializer(source='activity', read_only=True)
    commitments = CommitmentTrackingSerializer(many=True, read_only=True)
    
    class Meta:
        model = EstimationDetail
        fields = [
            'id', 'estimation', 'concept', 'concept_detail', 'volume', 'amount',
            'execution_date', 'commitment_status', 'activity', 'activity_detail',
            'imported_from_schedule', 'commitments'
        ]
        read_only_fields = ['id']
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("El monto debe ser mayor que cero.")
        return value
    
    def validate_concept(self, value):
        if not Concept.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("El concepto no existe.")
        return value

class EstimationListSerializer(serializers.ModelSerializer):
    detail_count = serializers.SerializerMethodField()
    construction_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Estimation
        fields = [
            'id', 'name', 'period_start', 'period_end', 'total_amount',
            'status', 'construction', 'construction_name', 'is_planned',
            'based_on_schedule', 'detail_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'total_amount', 'created_at', 'updated_at']
    
    def get_detail_count(self, obj):
        return obj.details.count()
    
    def get_construction_name(self, obj):
        return obj.construction.name if obj.construction else None

class EstimationDetailedSerializer(serializers.ModelSerializer):
    details = EstimationDetailSerializer(many=True, read_only=True)
    construction_name = serializers.SerializerMethodField()
    schedule_name = serializers.SerializerMethodField()
    created_by_username = serializers.SerializerMethodField()
    
    class Meta:
        model = Estimation
        fields = [
            'id', 'name', 'period_start', 'period_end', 'total_amount',
            'status', 'construction', 'construction_name', 'is_planned',
            'based_on_schedule', 'schedule', 'schedule_name', 'created_by',
            'created_by_username', 'details', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'total_amount', 'created_at', 'updated_at']
    
    def get_construction_name(self, obj):
        return obj.construction.name if obj.construction else None
    
    def get_schedule_name(self, obj):
        return obj.schedule.name if obj.schedule else None
    
    def get_created_by_username(self, obj):
        return obj.created_by.username if obj.created_by else None

class EstimationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Estimation
        fields = [
            'id', 'name', 'period_start', 'period_end', 'total_amount', 'status',
            'construction', 'is_planned', 'based_on_schedule', 'schedule', 
            'created_by', 'created_at', 'updated_at'
        ]
    
    def validate_name(self, value):
        if not value:
            raise serializers.ValidationError("El nombre de la estimación no puede estar vacío.")
        return value
    
    def validate(self, data):
        if 'period_start' in data and 'period_end' in data:
            if data['period_start'] > data['period_end']:
                raise serializers.ValidationError("La fecha de inicio no puede ser posterior a la fecha de fin.")
        return data