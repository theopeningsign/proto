// ResultViewer.js 수정 부분 (SignboardTransform 컴포넌트 호출 부분)

// ... 기존 코드 ...

<SignboardTransform
  key={`${originalSignboards[0]?.formData?.fontSize || 100}-${originalSignboards[0]?.formData?.rotation || 0}`}
  signboards={originalSignboards.map((sb, idx) => ({
    id: idx,
    polygon_points: selectedArea ? (selectedArea.type === 'polygon' 
      ? selectedArea.points.map(p => [p.x, p.y])
      : [[selectedArea.x, selectedArea.y], 
         [selectedArea.x + selectedArea.width, selectedArea.y],
         [selectedArea.x + selectedArea.width, selectedArea.y + selectedArea.height],
         [selectedArea.x, selectedArea.y + selectedArea.height]])
      : [],
    text: sb.formData?.text || ''
  }))}
  originalSignboards={originalSignboards}
  imageSize={imageSize}
  selectedArea={selectedArea}  // 추가
  textSizeInfo={textSizeInfo}  // 추가
  onTransformChange={setPendingTransforms}
  onApply={handleApplyTransforms}
/>

// ... 기존 코드 ...
