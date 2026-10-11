"""
dev/calibrate_router.py

Router calibration and continuous learning script.

Analyzes router performance from production data and suggests threshold adjustments.
Supports:
- Threshold tuning for accuracy vs cost balance
- Performance metrics (precision, recall, F1)
- Continuous learning from new conversations
- What-if analysis for different thresholds
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select, and_
from db.engine import init_db, close_db, get_db_session
from db.models import ConversationMessage
from src.router import RouteLLMRouter, get_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def analyze_router_performance() -> Dict:
    """
    Analyze router's historical performance from database.
    
    Returns metrics:
    - Accuracy: How often router made correct decision
    - Precision: Of local predictions, how many were actually good
    - Recall: Of queries that could use local, how many were routed there
    - F1 Score: Harmonic mean of precision and recall
    - Token savings: Actual savings achieved
    """
    logger.info("Analyzing router performance from production data...")
    
    await init_db()
    
    # Metrics
    total_predictions = 0
    correct_predictions = 0
    
    # Confusion matrix
    true_local = 0    # Router said local, was correct
    false_local = 0   # Router said local, should have been cloud
    true_cloud = 0    # Router said cloud, was correct
    false_cloud = 0   # Router said cloud, could have been local
    
    total_tokens_used = 0
    total_tokens_saved = 0
    total_cost = 0.0
    total_savings = 0.0
    
    async with get_db_session() as session:
        # Get all assistant messages with router decisions
        result = await session.execute(
            select(ConversationMessage)
            .where(
                and_(
                    ConversationMessage.role == "assistant",
                    ConversationMessage.router_confidence.isnot(None),
                )
            )
            .order_by(ConversationMessage.created_at)
        )
        messages = result.scalars().all()
        
        logger.info(f"Found {len(messages)} messages with router decisions")
        
        for msg in messages:
            total_predictions += 1
            
            backend = msg.backend
            router_score = msg.router_score or 0.0
            router_confidence = msg.router_confidence or 0.5
            
            # Determine ground truth (what SHOULD have happened)
            # Use quality_passed as signal if available, otherwise assume correct
            if msg.quality_passed is not None:
                # If local was used and quality passed, local was correct
                # If cloud was used, assume it was necessary
                ground_truth = "local" if (backend == "local" and msg.quality_passed) else "cloud"
            else:
                # No quality data - assume router was correct
                ground_truth = backend
            
            # Determine prediction (what router decided)
            predicted = backend
            
            # Update confusion matrix
            if predicted == "local" and ground_truth == "local":
                true_local += 1
                correct_predictions += 1
            elif predicted == "local" and ground_truth == "cloud":
                false_local += 1
            elif predicted == "fireworks" and ground_truth == "cloud":
                true_cloud += 1
                correct_predictions += 1
            elif predicted == "fireworks" and ground_truth == "local":
                false_cloud += 1
            
            # Track economics
            total_tokens_used += msg.tokens_used
            total_tokens_saved += msg.tokens_saved
            total_cost += msg.cost_usd
            total_savings += msg.savings_usd
    
    await close_db()
    
    # Calculate metrics
    accuracy = correct_predictions / max(1, total_predictions)
    
    # Precision: Of local predictions, how many were correct
    precision = true_local / max(1, true_local + false_local)
    
    # Recall: Of queries that could use local, how many did
    recall = true_local / max(1, true_local + false_cloud)
    
    # F1 Score
    f1 = 2 * (precision * recall) / max(0.001, precision + recall)
    
    # Token efficiency
    total_tokens = total_tokens_used + total_tokens_saved
    savings_rate = total_tokens_saved / max(1, total_tokens)
    
    metrics = {
        "total_predictions": total_predictions,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "confusion_matrix": {
            "true_local": true_local,
            "false_local": false_local,
            "true_cloud": true_cloud,
            "false_cloud": false_cloud,
        },
        "economics": {
            "tokens_used": total_tokens_used,
            "tokens_saved": total_tokens_saved,
            "total_tokens": total_tokens,
            "savings_rate": savings_rate,
            "total_cost_usd": total_cost,
            "total_savings_usd": total_savings,
        }
    }
    
    return metrics


def print_performance_report(metrics: Dict):
    """Pretty-print performance metrics."""
    logger.info("\n" + "=" * 70)
    logger.info("ROUTER PERFORMANCE REPORT")
    logger.info("=" * 70)
    
    logger.info(f"\n📊 Classification Metrics ({metrics['total_predictions']} predictions)")
    logger.info(f"  Accuracy:  {metrics['accuracy']:.1%} (overall correctness)")
    logger.info(f"  Precision: {metrics['precision']:.1%} (local predictions that were correct)")
    logger.info(f"  Recall:    {metrics['recall']:.1%} (local opportunities captured)")
    logger.info(f"  F1 Score:  {metrics['f1_score']:.3f} (harmonic mean)")
    
    cm = metrics['confusion_matrix']
    logger.info(f"\n🎯 Confusion Matrix")
    logger.info(f"  True Local:   {cm['true_local']:3d} ✓ (correctly routed to local)")
    logger.info(f"  False Local:  {cm['false_local']:3d} ✗ (routed to local, should be cloud)")
    logger.info(f"  True Cloud:   {cm['true_cloud']:3d} ✓ (correctly routed to cloud)")
    logger.info(f"  False Cloud:  {cm['false_cloud']:3d} ✗ (routed to cloud, could be local)")
    
    econ = metrics['economics']
    logger.info(f"\n💰 Token Economics")
    logger.info(f"  Tokens Used:  {econ['tokens_used']:,} (cloud)")
    logger.info(f"  Tokens Saved: {econ['tokens_saved']:,} (local)")
    logger.info(f"  Savings Rate: {econ['savings_rate']:.1%}")
    logger.info(f"  Total Cost:   ${econ['total_cost_usd']:.4f}")
    logger.info(f"  Savings:      ${econ['total_savings_usd']:.4f}")
    
    # Recommendations
    logger.info(f"\n💡 Recommendations")
    
    if metrics['precision'] < 0.85:
        logger.info(f"  ⚠️  Low precision ({metrics['precision']:.1%}) - router routing too much to local")
        logger.info(f"     Consider increasing threshold to be more conservative")
    
    if metrics['recall'] < 0.70:
        logger.info(f"  ⚠️  Low recall ({metrics['recall']:.1%}) - missing local opportunities")
        logger.info(f"     Consider decreasing threshold to route more to local")
    
    if metrics['accuracy'] >= 0.90:
        logger.info(f"  ✅ Excellent accuracy ({metrics['accuracy']:.1%}) - router performing well")
    elif metrics['accuracy'] >= 0.80:
        logger.info(f"  ✓  Good accuracy ({metrics['accuracy']:.1%}) - room for improvement")
    else:
        logger.info(f"  ⚠️  Accuracy needs improvement ({metrics['accuracy']:.1%})")
        logger.info(f"     Consider retraining with more data")
    
    if econ['savings_rate'] < 0.50:
        logger.info(f"  💡 Savings rate is {econ['savings_rate']:.1%} - potential for more local routing")
    elif econ['savings_rate'] > 0.80:
        logger.info(f"  ✅ Excellent savings rate ({econ['savings_rate']:.1%})")


async def suggest_threshold_adjustment(metrics: Dict) -> float:
    """
    Suggest optimal threshold based on performance.
    
    Strategy:
    - If false_local > 0: Too aggressive, increase threshold (more cloud)
    - If false_cloud > false_local: Too conservative, decrease threshold (more local)
    - Balance accuracy with cost savings
    """
    cm = metrics['confusion_matrix']
    current_threshold = 0.0  # Default
    
    logger.info("\n" + "=" * 70)
    logger.info("THRESHOLD TUNING SUGGESTIONS")
    logger.info("=" * 70)
    
    # Calculate error rates
    total = sum(cm.values())
    false_local_rate = cm['false_local'] / max(1, total)
    false_cloud_rate = cm['false_cloud'] / max(1, total)
    
    logger.info(f"\nCurrent threshold: {current_threshold:.3f}")
    logger.info(f"False local rate: {false_local_rate:.1%} (local failed, needed cloud)")
    logger.info(f"False cloud rate: {false_cloud_rate:.1%} (used cloud, could use local)")
    
    # Adjustment logic
    if false_local_rate > 0.10:
        # Too many local failures - be more conservative
        adjustment = 0.2
        suggested = current_threshold + adjustment
        logger.info(f"\n⚠️  High false local rate ({false_local_rate:.1%})")
        logger.info(f"   Suggestion: INCREASE threshold to {suggested:.3f} (+{adjustment:.3f})")
        logger.info(f"   Effect: Route more queries to cloud for better accuracy")
        logger.info(f"   Trade-off: Higher cost, better quality")
    
    elif false_cloud_rate > false_local_rate * 2:
        # Missing too many local opportunities
        adjustment = -0.15
        suggested = current_threshold + adjustment
        logger.info(f"\n💡 High false cloud rate ({false_cloud_rate:.1%})")
        logger.info(f"   Suggestion: DECREASE threshold to {suggested:.3f} ({adjustment:.3f})")
        logger.info(f"   Effect: Route more queries to local for better savings")
        logger.info(f"   Trade-off: Lower cost, maintain quality")
    
    else:
        suggested = current_threshold
        logger.info(f"\n✅ Threshold appears well-balanced")
        logger.info(f"   Keep current threshold: {current_threshold:.3f}")
        logger.info(f"   Accuracy: {metrics['accuracy']:.1%}, Savings: {metrics['economics']['savings_rate']:.1%}")
    
    logger.info(f"\n📝 To apply adjustment:")
    logger.info(f"   router = get_router()")
    logger.info(f"   router.threshold = {suggested:.3f}")
    logger.info(f"   router.save('models/router.pkl')")
    
    return suggested


async def incremental_retrain():
    """
    Incrementally retrain router with new conversation data.
    
    This allows continuous learning from production usage.
    """
    logger.info("\n" + "=" * 70)
    logger.info("INCREMENTAL RETRAINING")
    logger.info("=" * 70)
    
    from dev.train_router import extract_training_data
    
    # Extract new training data
    prompts, labels = await extract_training_data()
    
    if len(prompts) < 10:
        logger.warning(f"Only {len(prompts)} training examples - need at least 10 for retraining")
        return
    
    logger.info(f"Extracted {len(prompts)} training examples from production")
    
    # Load existing router
    router = get_router("models/router.pkl")
    
    if not router.is_trained:
        logger.warning("Router not yet trained. Run dev/train_router.py first")
        return
    
    # Retrain with new data
    logger.info("Retraining router with production data...")
    router.train(
        prompts=prompts,
        labels=labels,
        learning_rate=0.005,  # Lower learning rate for fine-tuning
        regularization=0.15,
    )
    
    # Save updated model
    router.save("models/router.pkl")
    logger.info("✓ Router retrained and saved")


async def main():
    """Main calibration workflow."""
    logger.info("=" * 70)
    logger.info("ROUTELLM CALIBRATION TOOL")
    logger.info("=" * 70)
    
    # 1. Analyze current performance
    metrics = await analyze_router_performance()
    
    if metrics['total_predictions'] == 0:
        logger.warning("\n⚠️  No router decisions found in database")
        logger.warning("   The router needs to process some queries first")
        logger.warning("   Run the application and generate conversations, then re-run calibration")
        return
    
    # 2. Print report
    print_performance_report(metrics)
    
    # 3. Suggest threshold adjustment
    suggested_threshold = await suggest_threshold_adjustment(metrics)
    
    # 4. Ask if user wants to retrain
    logger.info("\n" + "=" * 70)
    logger.info("NEXT STEPS")
    logger.info("=" * 70)
    logger.info("\n1. Review the metrics above")
    logger.info("2. Adjust threshold if needed (see suggestions)")
    logger.info("3. For significant changes, retrain router with new data")
    
    logger.info("\n💾 To retrain router with production data:")
    logger.info("   python dev/train_router.py")
    
    logger.info("\n✓ Calibration complete!")


if __name__ == "__main__":
    asyncio.run(main())
