function setupCoverPreviews(){
 document.querySelectorAll('[data-cover-preview]:not([data-cover-ready])').forEach(input=>{
 input.dataset.coverReady='';
 let blob;
 input.addEventListener('change',()=>{const file=input.files[0],preview=document.getElementById(input.dataset.coverPreview);input.setCustomValidity('');if(!file)return;if(file.size>5*1024*1024){input.value='';input.setCustomValidity('Chọn ảnh tối đa 5 MB.');input.reportValidity();return;}if(blob)URL.revokeObjectURL(blob);blob=URL.createObjectURL(file);preview.src=blob;preview.hidden=false;});
});
}
setupCoverPreviews();
document.addEventListener('library:content-updated',setupCoverPreviews);
