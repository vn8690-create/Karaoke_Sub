import { beforeEach, describe, expect, it } from 'vitest';
import { useKaraoke } from '../src/karaokeStore';
import { lStart, makeLine } from '../src/karaoke';

const L = () => [makeLine('Xin chào các bạn', 1, 5)!, makeLine('Tạm biệt nhé', 6, 9)!];
beforeEach(() => useKaraoke.setState({ lines: [], past: [], future: [], offset: 0, source: 'none', sel: undefined, selEdge: undefined, dirty: false }));
describe('karaoke store', () => {
  it('nạp lời rồi hoàn tác quay về trạng thái rỗng, làm lại khôi phục', () => {
    const k = useKaraoke.getState(); k.load(L(), 'file'); expect(useKaraoke.getState().lines).toHaveLength(2);
    useKaraoke.getState().undo(); expect(useKaraoke.getState().lines).toHaveLength(0); useKaraoke.getState().redo(); expect(useKaraoke.getState().lines).toHaveLength(2);
  });
  it('kéo mép nhiều lần chỉ cần một bước hoàn tác (commit lúc bắt đầu kéo)', () => {
    useKaraoke.getState().load(L(), 'file'); const l = useKaraoke.getState().lines[0], before = l.words[1].end;
    useKaraoke.getState().commit(); for (let i = 1; i <= 5; i++) useKaraoke.getState().moveEdge(l.id, 3, before + i * 0.01);
    expect(useKaraoke.getState().lines[0].words[1].end).toBeCloseTo(before + 0.05, 3); expect(useKaraoke.getState().dirty).toBe(true);
    useKaraoke.getState().undo(); expect(useKaraoke.getState().lines[0].words[1].end).toBeCloseTo(before, 3);
  });
  it('sửa chữ nhiều lần sau một commit vẫn hoàn tác một lần', () => {
    useKaraoke.getState().load(L(), 'file'); const id = useKaraoke.getState().lines[0].id; useKaraoke.getState().commit();
    for (const t of ['A', 'A B', 'A B C']) useKaraoke.getState().editText(id, t);
    expect(useKaraoke.getState().lines[0].words).toHaveLength(3); useKaraoke.getState().undo(); expect(useKaraoke.getState().lines[0].words).toHaveLength(4);
  });
  it('áp dụng offset ghi vào mốc, đưa offset về 0 và hoàn tác được', () => {
    useKaraoke.getState().load(L(), 'file'); const s0 = lStart(useKaraoke.getState().lines[0]);
    useKaraoke.setState({ offset: 0.5 }); useKaraoke.getState().bakeOffset();
    expect(lStart(useKaraoke.getState().lines[0])).toBeCloseTo(s0 + 0.5, 3); expect(useKaraoke.getState().offset).toBe(0);
    useKaraoke.getState().undo(); expect(lStart(useKaraoke.getState().lines[0])).toBeCloseTo(s0, 3);
  });
  it('thêm và xoá câu có hoàn tác', () => {
    useKaraoke.getState().load(L(), 'file'); const first = useKaraoke.getState().lines[0].id; useKaraoke.getState().insert(first, 'Câu mới');
    expect(useKaraoke.getState().lines).toHaveLength(3); const added = useKaraoke.getState().sel!; useKaraoke.getState().remove(added);
    expect(useKaraoke.getState().lines).toHaveLength(2); useKaraoke.getState().undo(); expect(useKaraoke.getState().lines).toHaveLength(3);
  });
});
