"""漏封仪分界值选择与盲验误判统计（纯函数，无 IO，便于独立验证）。

规则：
- 读数达到分界（reading >= cutoff）即判“漏封”，否则判“合格”。
- 候选分界只从校准组试件的实测读数中产生。
- 误判 = 仪器判定与人工复判不一致。
- 选误判数最少的分界；误判数相同取较小分界。
"""

LEAK = 'leak'
SEALED = 'sealed'
LABELS = (LEAK, SEALED)


def instrument_judges_leak(reading, cutoff):
    return reading >= cutoff


def misjudged(reading, rejudgement, cutoff):
    predicts_leak = instrument_judges_leak(reading, cutoff)
    actual_leak = rejudgement == LEAK
    return predicts_leak != actual_leak


def count_misjudgements(specimens, cutoff):
    return sum(1 for s in specimens if misjudged(s['reading'], s['rejudgement'], cutoff))


def choose_cutoff(specimens):
    """从校准组实测读数中选分界。

    specimens: [{'reading': float, 'rejudgement': 'leak'|'sealed'}, ...]
    返回 (cutoff, misjudgement_count, candidate_table)。
    校准组为空、缺读数/复判时抛 ValueError。
    """
    if not specimens:
        raise ValueError('校准组没有试件，无法选择分界')
    cleaned = []
    for s in specimens:
        if s.get('reading') is None or s.get('rejudgement') is None:
            raise ValueError('校准组试件读数与复判必须完整')
        reading = float(s['reading'])
        label = s['rejudgement']
        if label not in LABELS:
            raise ValueError('复判只允许 leak（漏封）或 sealed（合格）')
        cleaned.append({'reading': reading, 'rejudgement': label})
    # 候选取校准组实测读数去重值，升序；同分取小值天然由遍历顺序保证
    candidates = sorted({s['reading'] for s in cleaned})
    table = []
    best = None
    for cutoff in candidates:
        n = count_misjudgements(cleaned, cutoff)
        table.append({'cutoff': cutoff, 'misjudgements': n})
        if best is None or n < best[1]:
            best = (cutoff, n)
    cutoff, total = best
    return cutoff, total, table


def blind_review(specimens, cutoff):
    """盲验揭晓：用冻结分界对盲验组逐件判定并统计误判。"""
    if not specimens:
        raise ValueError('盲验组没有试件，无法揭晓')
    details = []
    total = 0
    for s in specimens:
        if s.get('reading') is None or s.get('rejudgement') is None:
            raise ValueError('盲验组仍有试件缺读数或复判')
        reading = float(s['reading'])
        label = s['rejudgement']
        if label not in LABELS:
            raise ValueError('复判只允许 leak（漏封）或 sealed（合格）')
        wrong = misjudged(reading, label, cutoff)
        total += int(wrong)
        details.append({
            'specimen_key': s.get('specimen_key'),
            'reading': reading,
            'rejudgement': label,
            'instrument': LEAK if instrument_judges_leak(reading, cutoff) else SEALED,
            'misjudged': wrong,
        })
    return total, details
