import {
  TrendingUp, TrendingDown, DollarSign, Users, ShoppingCart,
  Activity, Target, Zap, Clock, Percent, BarChart3,
  Package, UserCheck, CreditCard, Flame, RefreshCw,
  Calendar, Scale, UserMinus, Hash, FileText, Database,
  AlertTriangle, ArrowUp, ArrowDown, Minus,
} from 'lucide-react';

/**
 * Business-category → Lucide icon component map.
 *
 * The AI selects `businessCategory` in the KPI payload; this map resolves
 * it to a real component so tree-shaking is preserved (no DynamicIcon).
 *
 * Add new categories here; add the icon import above.
 */
const CATEGORY_ICON_MAP = {
  revenue:          DollarSign,
  cost:             CreditCard,
  growth:           TrendingUp,
  users:            Users,
  customers:        Users,
  churn_risk:       UserMinus,
  rate_metric:      Percent,
  volume:           ShoppingCart,
  price:            DollarSign,
  performance:      Target,
  duration:         Clock,
  quantity:         Package,
  retention:        RefreshCw,
  engagement:       Activity,
  conversion:       TrendingUp,
  satisfaction:     UserCheck,
  quality:          BarChart3,
  activity:         Activity,
  count:            Hash,
  file:             FileText,
  data:             Database,
  anomaly:          AlertTriangle,
  // Fallback
  neutral:          BarChart3,
  unknown:          BarChart3,
};

const DEFAULT_ICON = BarChart3;

/**
 * Resolve a business category string to a Lucide icon component.
 *
 * @param {string} category  - The `kpi.businessCategory` value from the backend.
 * @param {string} [overrideIcon] - Optional specific icon name override.
 * @returns {React.ComponentType} A Lucide icon component.
 */
export function resolveMetricIcon(category, overrideIcon) {
  if (overrideIcon && CATEGORY_ICON_MAP[overrideIcon]) {
    return CATEGORY_ICON_MAP[overrideIcon];
  }
  return CATEGORY_ICON_MAP[category] || DEFAULT_ICON;
}

/**
 * Trend direction → icon component.
 */
export function trendIcon(direction) {
  if (direction === 'up') return TrendingUp;
  if (direction === 'down') return TrendingDown;
  return Minus;
}

export { CATEGORY_ICON_MAP };
export default resolveMetricIcon;
