import os
from django import forms
from django.conf import settings
from .bin2real import *
from .models import *

class BinStructForm(forms.ModelForm):
    class Meta:
        model = BinStruct
        fields = '__all__'

    def save(self, commit=True, bs_id=None):
        if bs_id is not None: # UPDATE
            bs = BinStruct.objects.get(id=bs_id)
            bs.label = self.cleaned_data['label']
            if commit:
                bs.save()
            obj = bs
        else: # INSERT
            obj = super().save(commit=commit)
        return obj

class BinFieldForm(forms.ModelForm):
    delete = forms.BooleanField(initial=False, widget=forms.HiddenInput(), required=False)

    class Meta:
        model = BinField
        fields = '__all__'
        widgets = {'bs': forms.HiddenInput()}

    def save(self, commit=True, bf=None):
        if bf is not None: # UPDATE
            bf.label = self.cleaned_data['label']
            bf.bits = self.cleaned_data['bits']
            bf.tf_coef0 = self.cleaned_data['tf_coef0']
            bf.tf_coef1 = self.cleaned_data['tf_coef1']
            if commit:
                bf.save()
            obj = bf
        else: # INSERT
            obj = super().save(commit=commit)
        return obj

class FileForm(forms.Form):
    uploads = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}), required=False)

    def clean(self):
        super().clean()

        # Check each file size for multiple files
        if not self.has_error('uploads'):
            files = self.files.getlist('uploads')
            for f in files:
                if f.size == 0:
                    raise ValidationError('The submitted file is empty.')

class SelectBinDataForm(forms.Form):
    bd = forms.ModelChoiceField(queryset=BinData.objects.all(), label='Data',
        widget=forms.Select(attrs={'class': 'sel'}))

class SelectBinStructForm(forms.Form):
    bs = forms.ModelChoiceField(queryset=BinStruct.objects.all(), label='Structure',
        widget=forms.Select(attrs={'class': 'sel', 'onChange': 'this.form.submit();'}))

class SelectGraphForm(forms.Form):
    SCATTER = 'id_scatter'
    SCATTER_3D = 'id_scatter_3d'
    LINE = 'id_line'
    LINE_3D = 'id_line_3d'
    GRAPH_TYPES = [
        # (Identifier, required number), display text
        ((SCATTER, 2), 'scatter'),
        ((SCATTER_3D, 3), 'scatter 3D'),
        ((LINE, 2), 'line'),
        ((LINE_3D, 3), 'line 3D'),
    ]
    graph = forms.ChoiceField(choices=GRAPH_TYPES,
        widget=forms.Select(attrs={'class': 'sel', 'onChange': 'this.form.submit();'}))

    @classmethod
    def get_id_str(cls, graph_id):
        return graph_id[0]

    @classmethod
    def get_required_num(cls, graph_id):
        return graph_id[1]

class SelectBinFieldForm(forms.Form):
    def __init__(self, choices, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['bf'] = forms.ChoiceField(choices=choices, 
            widget=forms.Select(attrs={'class': 'small_sel'}))

class GraphOption(forms.Form):
    width = forms.DecimalField(min_value=10, initial=1024,
        widget=forms.NumberInput(attrs={'class': 'small_sel'}))
    height = forms.DecimalField(min_value=10, initial=512,
        widget=forms.NumberInput(attrs={'class': 'small_sel'}))

    def __str__(self):
        return str(self.fields.get('width')) + ', ' + str(self.fields.get('height'))

    def get(self, label):
        if not hasattr(self, 'cleaned_data'):
            self.full_clean()
        return self.cleaned_data.get(label)

def get_binstruct_formset(data=None):
    FormSetClass = forms.modelformset_factory(model=BinStruct, exclude=[], 
        can_delete=True, extra=0)
    return FormSetClass(data=data)

def get_binfield_formset(srctype='', src=None):
    extra = 0
    data = None
    queryset = BinField.objects.none()
    initial = None

    if srctype == 'post': # Get formset from request.POST
        data = src
    elif srctype == 'bs_id': # Get formset belongs to bs_id's BinStruct
        queryset=BinField.objects.filter(bs__id=src)
    elif srctype == 'formset_append': # Get formset with an extra form
        bf_fs = src
        if not hasattr(bf_fs, 'cleaned_data'):
            bf_fs.full_clean()
        values = []
        for form in bf_fs:
            values.append(_get_binfield_value_from_form(form))
        initial = values
        extra = len(values) + 1
    elif srctype == 'formset_delete': # Get formset after deleting a form
        bf_fs = src
        if not hasattr(bf_fs, 'cleaned_data'):
            bf_fs.full_clean()
        values = []
        for form in bf_fs:
            if 'delete' not in form.changed_data:
                values.append(_get_binfield_value_from_form(form))
        initial = values
        extra = len(values)
    else: # Get formset with an empty form
        extra = 1

    # Get formset class from factory
    FormSetClass = forms.modelformset_factory(model=BinField, form=BinFieldForm,
        exclude=[], extra=extra)
    return FormSetClass(data=data, queryset=queryset, initial=initial)

def _get_binfield_value_from_form(form):
    id = form.cleaned_data.get('id')
    label = form.cleaned_data.get('label', BinField._meta.get_field('label').default)
    bits = form.cleaned_data.get('bits', BinField._meta.get_field('bits').default)
    tf_coef0 = form.cleaned_data.get('tf_coef0', BinField._meta.get_field('tf_coef0').default)
    tf_coef1 = form.cleaned_data.get('tf_coef1', BinField._meta.get_field('tf_coef1').default)
    return {
        'id': id,
        'label': label,
        'bits': bits,
        'tf_coef0': tf_coef0,
        'tf_coef1': tf_coef1}

def get_binfield_label(bf_id):
    label = None
    if bf_id == BinField.INDEX_LABEL:
        label = BinField.INDEX_LABEL
    else:
        bf = BinField.objects.get(id=bf_id)
        if bf:
            label = bf.label
    return label

def save_binstruct_binfield_formset(bs_form, bs_id, bf_fs):
    err_msgs = []

    # Add error messages if form is invalid
    if not bs_form.is_valid():
        err_msgs.extend(_get_err_msgs_from_form(bs_form))
    if not bf_fs.is_valid():
        for form in bf_fs:
            err_msgs.extend(_get_err_msgs_from_form(form))
    makable, err_msg = CustomBinStruct.check_makable(
        sum([form.cleaned_data.get('bits', 0) for form in bf_fs]))
    if not makable:
        err_msgs.append(err_msg)

    # Save if all forms are valid
    if len(err_msgs) == 0:
        
        # Save BinStruct and BinField
        bs = bs_form.save(bs_id=bs_id)
        bf_ids = []
        for form in bf_fs:
            form.instance.bs = bs
            bf = form.save(bf=form.cleaned_data.get('id'))
            bf_ids.append(bf.id)
            
        # Delete BinField which is not exist in bf_fs
        del_bfs = BinField.objects.filter(bs__id=bs_id).exclude(pk__in=bf_ids)
        for bf in del_bfs:
            bf.delete()
        valid = True
    return err_msgs

def delete_binstruct_formset(bs_fs):
    if not hasattr(bs_fs, 'cleaned_data'):
        bs_fs.full_clean()
    for form in bs_fs:
        if form.cleaned_data.get('DELETE'):
            bs = form.save(commit=False)
            bs.delete()

def get_bindata_formset(data=None):
    FormSetClass = forms.modelformset_factory(model=BinData, exclude=[], 
        can_delete=True, extra=0)
    return FormSetClass(data=data)

def delete_bindata_formset(bd_fs):
    if not hasattr(bd_fs, 'cleaned_data'):
        bd_fs.full_clean()
    for form in bd_fs:
        if form.cleaned_data.get('DELETE'):
            bd = form.save(commit=False)
            bd.delete()

def save_fileform(form):
    err_msgs = []
    if form.is_valid():
        files = form.files.getlist('uploads')
        for f in files:
            bd = BinData(file=f, fname=f.name)
            bd.save()
    else:
        err_msgs = _get_err_msgs_from_form(form)
    return err_msgs

def _get_err_msgs_from_form(form):
    err_msgs = []
    for ves in form.errors.as_data().values():
            for ve in ves:
                for msg in ve.messages:
                    err_msgs.append(msg)
    return err_msgs

def make_bindata_path(year, month, day, fname):
    fname = fname.replace('/', '')
    fpath = os.path.join(settings.MEDIA_ROOT, settings.UPLOAD_ROOT, year, month, day, fname)
    return fpath.replace('\\', '/')

def get_bindata_path(bd):
    fpath = None
    if bd:
        fpath = bd.file.path
    return fpath

def get_select_binfield_forms(bs, num, initials):
    forms = []
    choices = [(BinField.INDEX_LABEL, BinField.INDEX_LABEL)]
    bf_ids = []
    for bf in BinField.objects.filter(bs=bs):
        choices.append((bf.id, bf.label))
    for i in range(num):
        sel_bf = SelectBinFieldForm(choices)
        if len(initials) == num:
            sel_bf.fields['bf'].initial = initials[i]
            bf_ids.append(sel_bf.fields['bf'].initial)
        forms.append(sel_bf)
    return forms, bf_ids
