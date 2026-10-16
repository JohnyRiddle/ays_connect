from rest_framework import serializers
from .models import TaskApproval, TaskApprovalEvent
from .approvals import actions


class ApprovalEventSerializer(serializers.ModelSerializer):
    actor_display = serializers.CharField(source='actor.display_name',read_only=True)
    class Meta:
        model=TaskApprovalEvent
        fields=('id','command_id','sequence','round_number','actor','actor_display','action','from_status','to_status','text','created_at')
        read_only_fields=fields


class ApprovalSerializer(serializers.ModelSerializer):
    history=ApprovalEventSerializer(many=True,read_only=True)
    requester_display=serializers.CharField(source='requester.display_name',read_only=True)
    approver_display=serializers.CharField(source='approver.display_name',read_only=True)
    available_actions=serializers.SerializerMethodField()
    class Meta:
        model=TaskApproval
        fields=('id','task','comment','requester','requester_display','approver','approver_display','source_body','source_internal','status','round_number','version','created_at','history','available_actions')
        read_only_fields=fields
    def get_available_actions(self,obj) -> list[str]:
        request=self.context['request']
        return actions(obj,getattr(request.user,'employee',None),request.user)


class ApprovalRequestSerializer(serializers.Serializer):
    comment=serializers.UUIDField(required=False,help_text="Optional existing comment. Omit to atomically publish the request text as a new chat message.")
    approver=serializers.UUIDField()
    text=serializers.CharField(max_length=10000,allow_blank=False,trim_whitespace=True)
    command_id=serializers.UUIDField(help_text='Idempotency key, reusable only for an identical command.')


class ApprovalCommandSerializer(serializers.Serializer):
    text=serializers.CharField(max_length=10000,allow_blank=False,trim_whitespace=True)
    version=serializers.IntegerField(min_value=1,help_text='Approval version, never Task.version.')
    command_id=serializers.UUIDField()


class ApprovalCandidateSerializer(serializers.Serializer):
    id=serializers.UUIDField()
    name=serializers.CharField()


class ApprovalErrorDetailSerializer(serializers.Serializer):
    code=serializers.CharField()
    message=serializers.CharField()
    details=serializers.JSONField()

class ApprovalErrorSerializer(serializers.Serializer):
    error=ApprovalErrorDetailSerializer()
