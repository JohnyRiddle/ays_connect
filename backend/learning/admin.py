from django.contrib import admin

from .models import AnswerOption, Assessment, AssessmentAttempt, AssessmentResponse, Certificate, Course, CourseAssignment, CourseAudience, CourseCategory, CourseModule, Lesson, LessonProgress, Question

admin.site.register([CourseCategory, Course, CourseAudience, CourseModule, Lesson, CourseAssignment, LessonProgress, Assessment, Question, AnswerOption, AssessmentAttempt, AssessmentResponse, Certificate])
