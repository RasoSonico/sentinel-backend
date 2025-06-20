from rest_framework import serializers
from .models import Schedule, Activity, ActivityConcept, CriticalPath, CriticalPathActivity
from catalogo.models import Concept
from catalogo.serializers import ConceptSerializer


class ActivityConceptSerializer(serializers.ModelSerializer):
    concept_detail = ConceptSerializer(source='concept', read_only=True)
    
    class Meta:
        model = ActivityConcept
        fields = ['id', 'concept', 'concept_detail', 'created_at']
        read_only_fields = ['id', 'created_at']


class ActivitySerializer(serializers.ModelSerializer):
    activity_concepts = ActivityConceptSerializer(many=True, read_only=True)
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    duration_days = serializers.IntegerField(read_only=True)
    concepts = serializers.PrimaryKeyRelatedField(
        many=True, 
        write_only=True, 
        queryset=Concept.objects.all(),
        required=False
    )
    
    class Meta:
        model = Activity
        fields = [
            'id','schedule','name', 'description', 'start_date', 'end_date',
            'progress_percentage', 'activity_concepts', 'total_amount',
            'duration_days', 'concepts', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        concepts = validated_data.pop('concepts', [])
        activity = Activity.objects.create(**validated_data)
        
        # Asociar conceptos con la actividad
        for concept in concepts:
            ActivityConcept.objects.create(activity=activity, concept=concept)
        
        return activity
    
    def update(self, instance, validated_data):
        concepts = validated_data.pop('concepts', None)
        
        # Actualizar los campos de la actividad
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Si se proporcionaron conceptos, actualizar las asociaciones
        if concepts is not None:
            # Eliminar asociaciones existentes
            instance.activity_concepts.all().delete()
            
            # Crear nuevas asociaciones
            for concept in concepts:
                ActivityConcept.objects.create(activity=instance, concept=concept)
        
        return instance


class CriticalPathActivitySerializer(serializers.ModelSerializer):
    activity_detail = ActivitySerializer(source='activity', read_only=True)
    
    class Meta:
        model = CriticalPathActivity
        fields = ['id', 'activity', 'activity_detail', 'sequence_order']
        read_only_fields = ['id']


class CriticalPathSerializer(serializers.ModelSerializer):
    critical_activities = CriticalPathActivitySerializer(many=True, read_only=True)
    
    class Meta:
        model = CriticalPath
        fields = ['id', 'schedule', 'calculated_at', 'notes', 'critical_activities', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ScheduleListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listar cronogramas"""
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    activity_count = serializers.SerializerMethodField()
    start_date = serializers.SerializerMethodField()
    end_date = serializers.SerializerMethodField()
    
    class Meta:
        model = Schedule
        fields = [
            'id', 'construction', 'name', 'description', 'is_active', 
            'total_amount', 'activity_count', 'start_date', 'end_date', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_activity_count(self, obj):
        return obj.activities.count()
    
    def get_start_date(self, obj):
        activities = obj.activities.all()
        if activities.exists():
            return activities.order_by('start_date').first().start_date
        return None
    
    def get_end_date(self, obj):
        activities = obj.activities.all()
        if activities.exists():
            return activities.order_by('-end_date').first().end_date
        return None


class ScheduleDetailSerializer(serializers.ModelSerializer):
    """Serializer completo con actividades para ver un cronograma detallado"""
    activities = ActivitySerializer(many=True, read_only=True)
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    critical_path = CriticalPathSerializer(read_only=True)
    
    class Meta:
        model = Schedule
        fields = [
            'id', 'construction', 'name', 'description', 'is_active',
            'activities', 'total_amount', 'critical_path', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']